from keep_alive import keep_alive
keep_alive()

print("✅ Flask keep-alive is running...")

import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")
BOTTOM_BORDER = "ﮩ٨ـﮩﮩ٨ـ✧ﮩ٨ـﮩﮩ٨"

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ─────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id,
        "👋 Hi! Welcome to *ASIDS Marketplace Bot*.\n\n"
        "To submit your ad, please send it in the following format:\n\n"
        "*TITLE*\n\n"
        "*DESCRIPTION (optional but appreciated)*\n\n"
        "_You can also attach a photo or video._"
    )

# ─────────────────────────────────────────
@bot.message_handler(content_types=['text', 'photo', 'video'])
def handle_ad_submission(message):
    if message.text and message.text.startswith('/'):
        return

    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    chat_id = message.chat.id
    caption = message.caption or message.text or "<No text>"

    lines = caption.strip().split('\n')
    if len(lines) == 0 or not lines[0].strip():
        bot.send_message(chat_id, "⚠️ Please include a *TITLE* for your ad on the first line.")
        return

    ad_preview = f"📬 New ad from {username}:\n\n{caption}"

    markup = types.InlineKeyboardMarkup()
    approve_btn = types.InlineKeyboardButton("✅ Approve", callback_data=f"approve|{chat_id}|{message.message_id}")
    reject_btn = types.InlineKeyboardButton("❌ Reject", callback_data=f"reject|{chat_id}|{message.message_id}")
    markup.add(approve_btn, reject_btn)

    if message.content_type == 'photo':
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=ad_preview, reply_markup=markup)
    elif message.content_type == 'video':
        bot.send_video(ADMIN_ID, message.video.file_id, caption=ad_preview, reply_markup=markup)
    else:
        bot.send_message(ADMIN_ID, ad_preview, reply_markup=markup)

    bot.send_message(chat_id, "✅ Your ad has been sent for approval!")

# ─────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def handle_decision(call):
    action, user_id, msg_id = call.data.split('|')
    user_id = int(user_id)
    msg_id = int(msg_id)

    try:
        original = bot.forward_message(ADMIN_ID, user_id, msg_id)
    except:
        bot.answer_callback_query(call.id, "❌ Could not find the original ad.")
        return

    caption = original.caption or original.text or "<No text>"
    final_msg = f"{caption}\n\n{BOTTOM_BORDER}"

    if action == "approve":
        if original.content_type == 'photo':
            bot.send_photo(CHANNEL_ID, original.photo[-1].file_id, caption=final_msg)
        elif original.content_type == 'video':
            bot.send_video(CHANNEL_ID, original.video.file_id, caption=final_msg)
        else:
            bot.send_message(CHANNEL_ID, final_msg)

        bot.send_message(user_id, "🎉 Your ad has been approved and posted!")
        bot.answer_callback_query(call.id, "✅ Approved and posted.")
    else:
        bot.send_message(user_id, "❌ Sorry, your ad has been rejected.")
        bot.answer_callback_query(call.id, "🚫 Rejected.")

bot.infinity_polling()
