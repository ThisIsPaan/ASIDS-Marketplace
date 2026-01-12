import logging
import os
# import nest_asyncio
# nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# ==========================================
# CONFIGURATION
# ==========================================
# Replace these with your actual values or set them as environment variables
TOKEN = os.environ.get("TOKEN", "8104825123:AAFHzmOszsHp0mQV6ZAYNPfwP2vGb_Mx0EU")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "920577321"))  # Replace 123456789 with your numeric Admin ID
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@asidmarketplace")  # Replace @mychannel with your channel username

# ==========================================
# LOGGING SETUP
# ==========================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# BOT LOGIC
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message."""
    await update.message.reply_text(
        "👋 Welcome! Send me any message (text, photo, video) and I'll forward it to the admin for review."
    )

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles messages from users: forwards to admin.
    Handles messages from admin: checks if it's a reply to forward to user.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    message = update.message
    
    # 1. ADMIN LOGIC: If message is from Admin
    if user.id == ADMIN_ID:
        # Check if Admin is replying to a message
        if message.reply_to_message:
            # Try to retrieve the original sender from bot_data using the message_id of the forwarded message
            # The forwarded message (or copy) in admin chat is 'message.reply_to_message'
            original_msg_id_in_admin_chat = message.reply_to_message.message_id
            
            user_data = context.bot_data.get(original_msg_id_in_admin_chat)
            
            if user_data:
                target_user_id = user_data['user_id']
                try:
                    # Copy the admin's reply to the user
                    await message.copy(chat_id=target_user_id)
                    await message.reply_text("✅ Reply sent to user.")
                except Exception as e:
                    logger.error(f"Failed to reply to user: {e}")
                    await message.reply_text(f"❌ Failed to send reply: {e}")
            else:
                await message.reply_text("⚠️ Could not find original sender. Bot might have restarted.")
        else:
            await message.reply_text("To reply to a user, reply to their forwarded message.")
        return

    # 2. USER LOGIC: Forward to Admin
    # Prepare Inline Keyboard
    keyboard = [
        [
            InlineKeyboardButton("Approve ✅", callback_data="approve"),
            InlineKeyboardButton("Decline ❌", callback_data="decline")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # We use copy_message to preserve content type (photo, video, text)
        # and attach the admin buttons.
        sent_msg = await message.copy(
            chat_id=ADMIN_ID,
            caption=message.caption_html if message.caption else None,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Store mapping: Admin's Message ID -> User Info
        # This allows us to know who to reply to or who to notify on Approve/Decline
        context.bot_data[sent_msg.message_id] = {
            'user_id': user.id,
            'original_message_id': message.message_id,
            'username': user.username,
            'first_name': user.first_name
        }
        
        await message.reply_text("📨 Message received! Waiting for admin approval.")
        logger.info(f"Forwarded message from {user.first_name} ({user.id}) to Admin.")
        
    except Exception as e:
        logger.error(f"Error forwarding to admin: {e}")
        await message.reply_text("❌ Error forwarding message. Please try again later.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Approve/Decline buttons."""
    query = update.callback_query
    await query.answer() # Acknowledge the click
    
    data = query.data
    admin_msg_id = query.message.message_id
    
    # Retrieve user info
    user_data = context.bot_data.get(admin_msg_id)
    
    if not user_data:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ Original user info lost (bot restarted). Cannot process.")
        return

    user_id = user_data['user_id']
    original_msg_id = user_data['original_message_id']
    
    if data == "approve":
        try:
            # Post to Channel
            # We copy the original message from the USER's chat to the CHANNEL
            await context.bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=user_id,
                message_id=original_msg_id
            )
            
            # Update Admin message
            # Fix: Handle messages with no caption or non-text messages correctly
            new_text = f"✅ <b>APPROVED</b>"
            if query.message.text:
                await query.edit_message_text(
                    text=f"{query.message.text}\n\n{new_text}",
                    parse_mode='HTML'
                )
            elif query.message.caption:
                await query.edit_message_caption(
                    caption=f"{query.message.caption}\n\n{new_text}",
                    parse_mode='HTML'
                )
            else:
                # If it's a media message without a caption, we can't "append" text easily to the caption if it doesn't exist
                # but we can try setting the caption now
                try:
                    await query.edit_message_caption(
                        caption=new_text,
                        parse_mode='HTML'
                    )
                except Exception:
                    # Fallback for messages that truly don't support captions or if edit fails
                    await query.edit_message_reply_markup(reply_markup=None)
                    await query.message.reply_text(new_text)
            
            # Notify User
            await context.bot.send_message(chat_id=user_id, text="✅ Your message was approved and posted!")
            logger.info(f"Approved message from {user_id}")
            
        except Exception as e:
            logger.error(f"Error approving: {e}")
            await query.message.reply_text(f"❌ Error posting to channel: {e}\nCheck permissions/ID.")

    elif data == "decline":
        # Update Admin message
        new_text = f"❌ <b>DECLINED</b>"
        if query.message.text:
            await query.edit_message_text(
                text=f"{query.message.text}\n\n{new_text}",
                parse_mode='HTML'
            )
        elif query.message.caption:
            await query.edit_message_caption(
                caption=f"{query.message.caption}\n\n{new_text}",
                parse_mode='HTML'
            )
        else:
            try:
                await query.edit_message_caption(
                    caption=new_text,
                    parse_mode='HTML'
                )
            except Exception:
                await query.edit_message_reply_markup(reply_markup=None)
                await query.message.reply_text(new_text)
        
        # Notify User
        await context.bot.send_message(chat_id=user_id, text="❌ Your message was declined by the admin.")
        logger.info(f"Declined message from {user_id}")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == '__main__':
    # Validation
    if "YOUR_BOT_TOKEN" in TOKEN:
        print("❌ ERROR: Please configure your TOKEN in bot.py")
        exit(1)

    print("🚀 Bot is starting...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Target Channel: {CHANNEL_ID}")

    # Build Application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle all messages that are NOT commands
    # filters.ALL includes text, photo, video, audio, etc.
    application.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_user_message))

    # Run
    print("✅ Bot is running. Press Ctrl+C to stop.")
    application.run_polling()
