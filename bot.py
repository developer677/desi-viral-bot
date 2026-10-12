import os
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# --- পরিবেশ থেকে কনফিগারেশন নেওয়া (Render থেকে সিক্রেট হিসেবে সেট হবে) ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
TARGET_CHANNEL_LINK = os.getenv("TARGET_CHANNEL_LINK")
REQUIRED_REFERRALS = 5

# --- ডাটাবেজ সেটাপ ---
conn = sqlite3.connect("bot_users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referred_by INTEGER,
    referral_count INTEGER DEFAULT 0,
    unlocked INTEGER DEFAULT 0
)
"""
)
conn.commit()


def add_user(user_id, referred_by=None):
  cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
  if cursor.fetchone() is None:
    cursor.execute(
        "INSERT INTO users (user_id, referred_by) VALUES (?, ?)",
        (user_id, referred_by),
    )
    conn.commit()
    if referred_by and referred_by != user_id:
      cursor.execute(
          "UPDATE users SET referral_count = referral_count + 1 WHERE user_id ="
          " ?",
          (referred_by,),
      )
      conn.commit()
      cursor.execute(
          "SELECT referral_count, unlocked FROM users WHERE user_id = ?",
          (referred_by,),
      )
      ref_data = cursor.fetchone()
      if ref_data and ref_data[0] >= REQUIRED_REFERRALS and ref_data[1] == 0:
        cursor.execute(
            "UPDATE users SET unlocked = 1 WHERE user_id = ?", (referred_by,)
        )
        conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  args = context.args

  referrer_id = None
  if args and args[0].isdigit():
    parsed_id = int(args[0])
    if parsed_id != user_id:
      referrer_id = parsed_id

  add_user(user_id, referrer_id)

  cursor.execute(
      "SELECT referral_count, unlocked FROM users WHERE user_id = ?", (user_id,)
  )
  user_data = cursor.fetchone()
  ref_count = user_data[0] if user_data else 0
  unlocked = user_data[1] if user_data else 0

  bot_username = context.bot.username
  ref_link = f"https://t.me/{bot_username}?start={user_id}"

  if unlocked == 1:
    text = (
        f"🎉 অভিনন্দন! আপনি সফলভাবে {REQUIRED_REFERRALS} জনকে রেফার করেছেন।\n\nনিচের"
        " বাটনে ক্লিক করে ৫ হাজার+ ভিডিওর চ্যানেলে জয়েন করে নিন! 👇"
    )
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔥 ৫০০০+ ভিডিও চ্যানেল ভিজিট করুন", url=TARGET_CHANNEL_LINK)]]
    )
  else:
    needed = REQUIRED_REFERRALS - ref_count
    text = (
        f"👋 স্বাগতম **Desi Viral 69** বটে!\n\n🔥 ৫ হাজার+ ভিডিওর এক্সক্লুসিভ চ্যানেল"
        f" আনলক করতে হলে অন্তত **{REQUIRED_REFERRALS} জন** বন্ধুর কাছে এই বট"
        " শেয়ার করতে হবে।\n\n📌 আপনার বর্তমান রেফার: **{ref_count}/{REQUIRED_REFERRALS}**"
        f" জন\n❌ আর মাত্র **{needed} জন** বাকি!"
    )
    share_url = f"https://t.me/share/url?url={ref_link}&text=🔥%20এখানে%20৫%20হাজার+%20ভিডিওর%20চ্যানেল%20পাবে!%20জলদি%20বটটি%20স্টার্ট%20করো:"
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 বন্ধুদের শেয়ার করুন", url=share_url)],
        [InlineKeyboardButton("🔄 স্ট্যাটাস চেক করুন", callback_data="check_status")],
    ])

  await update.message.reply_text(
      text, reply_markup=reply_markup, parse_mode="Markdown"
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  user_id = query.from_user.id

  cursor.execute(
      "SELECT referral_count, unlocked FROM users WHERE user_id = ?", (user_id,)
  )
  user_data = cursor.fetchone()
  ref_count = user_data[0] if user_data else 0
  unlocked = user_data[1] if user_data else 0

  if unlocked == 1:
    text = (
        f"🎉 অভিনন্দন! আপনার টার্গেট পূরণ হয়েছে।\n\n৫ হাজার+ ভিডিওর চ্যানেলের লিংক"
        " নিচে দেওয়া হলো: 👇"
    )
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔥 ৫০০০+ ভিডিও চ্যানেল ভিজিট করুন", url=TARGET_CHANNEL_LINK)]]
    )
    await query.edit_message_text(text, reply_markup=reply_markup)
  else:
    needed = REQUIRED_REFERRALS - ref_count
    await query.answer(
        f"আপনার বর্তমান রেফার {ref_count} জন। আরও {needed} জন বাকি আছে!",
        show_alert=True,
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  if user_id != ADMIN_ID:
    await update.message.reply_text("দুঃখিত, এই কমান্ডটি শুধু এডমিনের জন্য!")
    return

  message_text = " ".join(context.args)
  if not message_text:
    await update.message.reply_text(
        "দয়া করে মেসেজসহ কমান্ড দিন। যেমন: `/broadcast আপনার নোটিশ`"
    )
    return

  cursor.execute("SELECT user_id FROM users")
  users = cursor.fetchall()

  success = 0
  failed = 0

  for (u_id,) in users:
    try:
      await context.bot.send_message(
          chat_id=u_id,
          text=f"📢 **বট আপডেট নোটিশ:**\n\n{message_text}",
          parse_mode="Markdown",
      )
      success += 1
    except Exception:
      failed += 1

  await update.message.reply_text(
      f"✅ ব্রডকাস্ট সম্পন্ন!\nসফল: {success}\nব্যর্থ: {failed}"
  )


def main():
  if not TOKEN:
    print("Error: TOKEN is missing!")
    return

  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("broadcast", broadcast))
  app.add_handler(CallbackQueryHandler(button_handler))

  print("Bot is running...")
  app.run_polling()


if __name__ == "__main__":
  main()
