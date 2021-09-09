import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ChatPermissions

from SaitamaRobot import TIGER_USERS, WHITELIST_USERS, dispatcher
from SaitamaRobot.modules.helper_funcs.chat_status import (
    bot_admin, can_restrict, connection_status, is_user_admin, user_admin,
    user_admin_no_reply)
from SaitamaRobot.modules.log_channel import loggable
from SaitamaRobot.modules.sql import antiflood_sql as sql
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler, Filters, MessageHandler, run_async
from telegram.utils.helpers import mention_html, escape_markdown
from SaitamaRobot import dispatcher
from SaitamaRobot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from SaitamaRobot.modules.helper_funcs.string_handling import extract_time
from SaitamaRobot.modules.log_channel import loggable
from SaitamaRobot.modules.sql import antiflood_sql as sql
from SaitamaRobot.modules.connection import connected
from SaitamaRobot.modules.helper_funcs.alternate import send_message
FLOOD_GROUP = 3


@run_async
@loggable
def check_flood(update, context) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]
    if not user:  # ignore channels
        return ""

    # ignore admins and whitelists
    if (is_user_admin(chat, user.id) or user.id in WHITELIST_USERS or
            user.id in TIGER_USERS):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            chat.kick_member(user.id)
            execstrings = ("Banned")
            tag = "BANNED"
        elif getmode == 2:
            chat.kick_member(user.id)
            chat.unban_member(user.id)
            execstrings = ("Kicked")
            tag = "KICKED"
        elif getmode == 3:
            context.bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(can_send_messages=False))
            execstrings = ("Muted")
            tag = "MUTED"
        elif getmode == 4:
            bantime = extract_time(msg, getvalue)
            chat.kick_member(user.id, until_date=bantime)
            execstrings = ("Banned for {}".format(getvalue))
            tag = "TBAN"
        elif getmode == 5:
            mutetime = extract_time(msg, getvalue)
            context.bot.restrict_chat_member(
                chat.id,
                user.id,
                until_date=mutetime,
                permissions=ChatPermissions(can_send_messages=False))
            execstrings = ("Muted for {}".format(getvalue))
            tag = "TMUTE"
        send_message(update.effective_message,
                     "Beep Boop! Boop Beep!\n{}!".format(execstrings))

        return "<b>{}:</b>" \
               "\n#{}" \
               "\n<b>User:</b> {}" \
               "\nFlooded the group.".format(tag, html.escape(chat.title),
                                             mention_html(user.id, user.first_name))

    except BadRequest:
        msg.reply_text(
            "I can't restrict people here, give me permissions first! Until then, I'll disable anti-flood."
        )
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#INFO" \
               "\nDon't have enough permission to restrict users so automatically disabled anti-flood".format(chat.title)


@run_async
@user_admin_no_reply
@bot_admin
def flood_button(update: Update, context: CallbackContext):
    bot = context.bot
    query = update.callback_query
    user = update.effective_user
    match = re.match(r"unmute_flooder\((.+?)\)", query.data)
    if match:
        user_id = match.group(1)
        chat = update.effective_chat.id
        try:
            bot.restrict_chat_member(
                chat,
                int(user_id),
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True))
            update.effective_message.edit_text(
                f"Unmuted by {mention_html(user.id, user.first_name)}.",
                parse_mode="HTML")
        except:
            pass


@run_async
@user_admin
@loggable
def set_flood(update, context) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    args = context.args
