import time

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CallbackQueryHandler
from telegram.message import Message
from telegram.update import Update
from telegram.error import TimedOut, BadRequest, RetryAfter
import time
import pytz	
import datetime	
from datetime import datetime
import psutil, shutil

from bot import AUTO_DELETE_MESSAGE_DURATION, LOGGER, bot, dispatcher, status_reply_dict, status_reply_dict_lock, \
                Interval, DOWNLOAD_STATUS_UPDATE_INTERVAL, RSS_CHAT_ID, rss_session, LOG_CHANNEL_ID, LOG_CHANNEL_LINK, LOG_UNAME, LOG_CHANNEL
from bot import *              
from bot.helper.ext_utils.bot_utils import get_readable_message, get_readable_time, setInterval, MirrorStatus
from bot.helper.ext_utils.bot_utils import *


def sendMessage(text: str, bot, update: Update):
    try:
        return bot.send_message(update.message.chat_id,
                            reply_to_message_id=update.message.message_id,
                            text=text, allow_sending_without_reply=True, parse_mode='HTMl', disable_web_page_preview=True)
    except RetryAfter as r:
        LOGGER.error(str(r))
        time.sleep(r.retry_after * 1.5)
        return sendMessage(text, bot, update)
    except Exception as e:
        LOGGER.error(str(e))
        return

def sendMarkup(text: str, bot, update: Update, reply_markup: InlineKeyboardMarkup):
    try:
        return bot.send_message(update.message.chat_id,
                            reply_to_message_id=update.message.message_id,
                            text=text, reply_markup=reply_markup, allow_sending_without_reply=True,
                            parse_mode='HTMl', disable_web_page_preview=True)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        time.sleep(r.retry_after * 1.5)
        return sendMarkup(text, bot, update, reply_markup)
    except Exception as e:
        LOGGER.error(str(e))
        return

def editMessage(text: str, message: Message, reply_markup=None):
    try:
        bot.edit_message_text(text=text, message_id=message.message_id,
                              chat_id=message.chat.id,reply_markup=reply_markup,
                              parse_mode='HTMl', disable_web_page_preview=True)
    except RetryAfter as r:
        LOGGER.warning(str(r))
        time.sleep(r.retry_after * 1.5)
        return editMessage(text, message, reply_markup)
    except Exception as e:
        LOGGER.error(str(e))
        return
        
def sendRss(text: str, bot):
    if rss_session is None:
        try:
            return bot.send_message(RSS_CHAT_ID, text, parse_mode='HTMl', disable_web_page_preview=True)
        except RetryAfter as r:
            LOGGER.warning(str(r))
            time.sleep(r.retry_after * 1.5)
            return sendRss(text, bot)
        except Exception as e:
            LOGGER.error(str(e))
    else:
        try:
            return rss_session.send_message(RSS_CHAT_ID, text, parse_mode='HTMl', disable_web_page_preview=True)
        except FloodWait as e:
            LOGGER.warning(str(e))
            time.sleep(e.x * 1.5)
            return sendRss(text, bot)
        except Exception as e:
            LOGGER.error(str(e))
            return

def deleteMessage(bot, message: Message):
    try:
        bot.delete_message(chat_id=message.chat.id,
                           message_id=message.message_id)
    except Exception as e:
        LOGGER.error(str(e))

def sendLogFile(bot, update: Update):
    with open('log.txt', 'rb') as f:
        bot.send_document(document=f, filename=f.name,
                          reply_to_message_id=update.message.message_id,
                          chat_id=update.message.chat_id)

def auto_delete_message(bot, cmd_message: Message, bot_message: Message):
    if AUTO_DELETE_MESSAGE_DURATION != -1:
        time.sleep(AUTO_DELETE_MESSAGE_DURATION)
        try:
            # Skip if None is passed meaning we don't want to delete bot xor cmd message
            deleteMessage(bot, cmd_message)
            deleteMessage(bot, bot_message)
        except AttributeError:
            pass

def delete_all_messages():
    with status_reply_dict_lock:
        for message in list(status_reply_dict.values()):
            try:
                deleteMessage(bot, message)
                del status_reply_dict[message.chat.id]
            except Exception as e:
                LOGGER.error(str(e))
                return

def update_all_messages():
    currentTime = get_readable_time((time.time() - botStartTime))
    msg = get_readable_message()
    msg, buttons = get_readable_message()
    with status_reply_dict_lock:
        for chat_id in list(status_reply_dict.keys()):
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id].text:
                if len(msg) == 0:
                    msg = "Starting DL"
                try:
                    keyboard = [[InlineKeyboardButton("Refresh", callback_data=str(ONE)),
                                 InlineKeyboardButton("Stats", callback_data=str(THREE)),],
                                [InlineKeyboardButton("Close Window", callback_data=str(TWO)),]]
                    editMessage(msg, status_reply_dict[chat_id], reply_markup=InlineKeyboardMarkup(keyboard))
                except Exception as e:
                    LOGGER.error(str(e))
                status_reply_dict[chat_id].text = msg


def sendStatusMessage(msg, bot):
    if len(Interval) == 0:
        Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
    progress, buttons = get_readable_message()
    with status_reply_dict_lock:
        if msg.message.chat.id in list(status_reply_dict.keys()):
            try:
                message = status_reply_dict[msg.message.chat.id]
                deleteMessage(bot, message)
                del status_reply_dict[msg.message.chat.id]
            except Exception as e:
                LOGGER.error(str(e))
                del status_reply_dict[msg.message.chat.id]
        if buttons == "":
            message = sendMessage(progress, bot, msg)
        else:
            message = sendMarkup(progress, bot, msg, buttons)
        status_reply_dict[msg.message.chat.id] = message
        
def sendLog(text: str, bot, update: Update, reply_markup: InlineKeyboardMarkup):
    try:
        return bot.send_message(f"{LOG_CHANNEL_ID}",
                             reply_to_message_id=update.message.message_id,
                             text=text, disable_web_page_preview=True, reply_markup=reply_markup, allow_sending_without_reply=True, parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))
        
def sendPrivate(text: str, bot, update: Update, reply_markup: InlineKeyboardMarkup):
    bot_d = bot.get_me()
    b_uname = bot_d.username
    
    try:
        return bot.send_message(update.message.from_user.id,
                             reply_to_message_id=update.message.message_id,
                             text=text, disable_web_page_preview=True, reply_markup=reply_markup, allow_sending_without_reply=True, parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))
        if "Forbidden" in str(e):
            uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
            botstart = f"http://t.me/{b_uname}?start=start"
            keyboard = [
            [InlineKeyboardButton("Start Bot", url = f"{botstart}")],
            [InlineKeyboardButton("Dump Channel", url = f"t.me/{LOG_CHANNEL_LINK}")]]
            sendMarkup(f"Dear {uname},\n\n<b>🇮‌ 🇫‌🇴‌🇺‌🇳‌🇩‌ 🇹‌🇭‌🇦‌🇹‌ 🇾‌🇴‌🇺‌ 🇭‌🇦‌🇻‌🇪‌🇳‌'🇹‌ 🇸‌🇹‌🇦‌🇷‌🇹‌🇪‌🇩‌ 🇲‌🇪‌ 🇮‌🇳‌ 🇵‌🇲‌ (🇵‌🇷‌🇮‌🇻‌🇦‌🇹‌🇪‌ 🇨‌🇭‌🇦‌🇹‌) 🇾‌🇪‌🇹‌.</b>\n\n<b>🇫‌🇷‌🇴‌🇲‌ 🇳‌🇴‌🇼‌ 🇴‌🇳‌ 🇮‌ 🇼‌🇮‌🇱‌🇱‌ 🇬‌🇮‌🇻‌🇪‌ 🇾‌🇴‌🇺‌ 🇱‌🇮‌🇳‌🇰‌🇸‌ 🇮‌🇳‌ 🇵‌🇲‌ (🇵‌🇷‌🇮‌🇻‌🇦‌🇹‌🇪‌ 🇨‌🇭‌🇦‌🇹‌) 🇴‌🇳‌🇱‌🇾‌.</b>\n\n<i><b>🇵‌🇱‌🇪‌🇦‌🇸‌🇪‌ 🇸‌🇹‌🇦‌🇷‌🇹‌ 🇲‌🇪‌ 🇮‌🇳‌ 🇵‌🇲‌ (🇵‌🇷‌🇮‌🇻‌🇦‌🇹‌🇪‌ 🇨‌🇭‌🇦‌🇹‌) & 🇩‌🇴‌🇳‌'🇹‌ 🇲‌🇮‌🇸‌🇸‌ 🇫‌🇺‌🇹‌🇺‌🇷‌🇪‌ 🇺‌🇵‌🇱‌🇴‌🇦‌🇩‌🇸‌.</b></i>\n\n<b>🇫‌🇷‌🇴‌🇲‌ 🇳‌🇴‌🇼‌ 🇬‌🇪‌🇹‌ 🇾‌🇴‌🇺‌🇷‌ 🇱‌🇮‌🇳‌🇰‌🇸‌ 🇫‌🇷‌🇴‌🇲‌ @{LOG_CHANNEL_LINK} </b>.", bot, update, reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
ONE, TWO, THREE = range(3)       

def refresh(update, context):
    query = update.callback_query
    query.edit_message_text(text="Refreshing Status...⏳")
    time.sleep(3)
    update_all_messages()
    
def close(update, context):
    chat_id  = update.effective_chat.id
    user_id = update.callback_query.from_user.id
    bot = context.bot
    query = update.callback_query
    admins = bot.get_chat_member(chat_id, user_id).status in ['creator', 'administrator'] or user_id in [OWNER_ID]
    if admins:
        delete_all_messages()
    else:
        query.answer(text="You Don't Have Admin Rights!", show_alert=True)
        
def pop_up_stats(update, context):
    query = update.callback_query
    stats = bot_sys_stats()
    query.answer(text=stats, show_alert=True)

def bot_sys_stats():
    currentTime = get_readable_time(time.time() - botStartTime)
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    total, used, free = shutil.disk_usage('.')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    stats = f"""
BOT UPTIME 🕐 : {currentTime}

CPU : {progress_bar(cpu)} {cpu}%
RAM : {progress_bar(mem)} {mem}%
DISK : {progress_bar(disk)} {disk}%
TOTAL : {total}


USED : {used} || FREE : {free}
SENT : {sent} || RECV : {recv}
"""
    return stats
    
    
def sendtextlog(text: str, bot, update: Update):
    try:
        return bot.send_message(f"{LOG_SEND_TEXT}",
                             reply_to_message_id=update.message.message_id,
                             text=text, disable_web_page_preview=True, allow_sending_without_reply=True, parse_mode='HTMl')
    except Exception as e:
        LOGGER.error(str(e))
    
dispatcher.add_handler(CallbackQueryHandler(refresh, pattern='^' + str(ONE) + '$'))
dispatcher.add_handler(CallbackQueryHandler(close, pattern='^' + str(TWO) + '$'))
dispatcher.add_handler(CallbackQueryHandler(pop_up_stats, pattern='^' + str(THREE) + '$'))