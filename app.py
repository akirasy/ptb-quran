#!/usr/bin/env python3

import configparser, datetime, json, logging, pathlib, pytz

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler, ContextTypes, Defaults

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger('Dev')

# Load app config and file paths
BASE_DIR = pathlib.Path(__file__).resolve().parent
FILE_PROGRESS = BASE_DIR.joinpath('progress.ini')
FILE_CONFIG = BASE_DIR.joinpath('config.ini')
cp_config = configparser.ConfigParser()
cp_config.read(FILE_CONFIG)
cp_progress = configparser.ConfigParser()
cp_progress.read(FILE_PROGRESS)

# Set up constants
BOT_TOKEN = cp_config.get('TelegramBot', 'Token')
GROUP_ID = cp_config.get('TelegramBot', 'GroupId')
INITIAL_POST_TIME = cp_config.get('QuranPosting', 'InitialPostTime')
POST_FREQUENCY = cp_config.getint('QuranPosting', 'PostFrequency')
MAX_POST_PER_DAY = cp_config.getint('QuranPosting', 'MaxPostPerDay')
AYAT_PER_POST = cp_config.getint('QuranPosting', 'AyatPerPost')
TRANSLATION_AVAILABLE = cp_config.getboolean('QuranJson', 'TranslationAvailable')
QURAN_JSON_FILENAME = cp_config.get('QuranJson', 'FileName')

# Load Quran in memory
quran_loader = json.loads(BASE_DIR.joinpath('surah-library', QURAN_JSON_FILENAME).read_text())

def set_quran_progress(surah, ayat):
    cp_progress.set('QuranProgress', 'Surah', str(surah))
    cp_progress.set('QuranProgress', 'Ayat', str(ayat))
    with open(FILE_PROGRESS, 'w') as opened_file:
        cp_progress.write(opened_file)

def change_config(initial_post_time=None, post_frequency=None, max_post_per_day=None, ayat_per_post=None):
    parameters = locals()
    for key in parameters.keys():
        value = parameters[key]
        if value:
            key_pascal = ''.join(word.title() for word in key.split('_'))
            cp_config.set('QuranPosting', key_pascal, value)
        else:
            pass
    with open(FILE_CONFIG, 'w') as opened_file:
        cp_config.write(opened_file)

def get_quran_progress():
    surah = cp_progress.getint('QuranProgress', 'Surah')
    ayat = cp_progress.getint('QuranProgress', 'Ayat')
    return {
            'surah_number' : surah,
            'ayat_number' : ayat
            }

def get_ayat_info(surah_number, ayat_number):
    surah = quran_loader[surah_number - 1] # quran_loader returns list start with 0
    surah_name = surah['name']
    surah_name_transliteration = surah['transliteration']
    surah_total_verses = surah['total_verses']
    surah_verses = surah['verses']
    ayat = surah_verses[ayat_number - 1] # quran_loader return verses as a list starts with 0
    ayat_original = ayat['text']
    if TRANSLATION_AVAILABLE:
        ayat_translation = ayat['translation']
    else:
        ayat_translation = ''
    return {
            'surah_name' : surah_name,
            'surah_name_transliteration' : surah_name_transliteration,
            'surah_total_verses' : surah_total_verses,
            'ayat_original' : ayat_original,
            'ayat_translation' : ayat_translation
            }

def construct_quran_message():
    # Load quran read progress
    quran_read_progress = get_quran_progress()
    surah_number = quran_read_progress['surah_number']
    ayat_number =  quran_read_progress['ayat_number']
    # Load quran info
    ayat_info = get_ayat_info(surah_number, ayat_number)
    # Set progression
    if ayat_number < ayat_info['surah_total_verses']:
        next_ayat_number = ayat_number + 1
        next_surah_number = surah_number
    else:
        if surah_number < 114:
            next_ayat_number = 1
            next_surah_number = surah_number + 1
        else:
            next_ayat_number = 1
            next_surah_number = 1
    set_quran_progress(next_surah_number, next_ayat_number)
    # Construct message text
    text  = f'<b> Surah {ayat_info["surah_name_transliteration"]} - Ayat: {ayat_number}</b>\n\n'
    text += f'{ayat_info["ayat_original"]}\n\n'
    text += f'{ayat_info["ayat_translation"]}'
    return text

def remove_all_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_jobs = context.job_queue.jobs()
    for job in current_jobs:
        if current_jobs:
            job.schedule_removal()
        else:
            pass

def add_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app_timezone = pytz.timezone("Asia/Kuala_Lumpur")
    initial_run_time = app_timezone.localize(datetime.datetime.strptime(INITIAL_POST_TIME,"%H:%M"))
    for i in range(MAX_POST_PER_DAY):
        run_time = initial_run_time + datetime.timedelta(minutes=i*POST_FREQUENCY)
        job = context.job_queue.run_daily(callback=send_ayat_quran, time=run_time, data={'GROUP_ID':GROUP_ID}, name=str(i))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('It\'s Quran reading time.')

async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text =  '<b>Usage instructions.</b>\n'
    text += '/start - Welcome message\n'
    text += '/help - Usage instructions\n'
    text += '/change_config - Change app config\n'
    text += '/change_progress - Set new quran read progress\n'
    text += '/reset_jobs - Remove all current jobs and create a new one with new configuration\n'
    text += '/show_config - Show current configuration\n'
    await update.message.reply_text(text)

async def show_current_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text =   '<b>Current configuration.</b>\n'
    text += f'Start post time: {INITIAL_POST_TIME}\n'
    text += f'Posting frequency: Every {POST_FREQUENCY} minutes\n'
    text += f'Max post: {MAX_POST_PER_DAY} per day\n'
    text += f'Ayat per post: {AYAT_PER_POST} ayat\n'
    await update.message.reply_text(text)

async def send_ayat_quran(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    text = ''
    for i in range(AYAT_PER_POST):
        text += construct_quran_message()
        text += '\n\n'
    await context.bot.send_message(chat_id=job.data['GROUP_ID'], text=text)

async def change_app_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_text = 'Wrong syntax. Choose option:\n1. initial_post_time\n2. post_frequency\n3. max_post_per_day\n4. ayat_per_post\n\n/change_config {option} {value}'
    if len(update.message.text.split()) < 3:
        await update.message.reply_text(error_text)
    else:
        command, config_parameter, value = update.message.text.split()
        match config_parameter:
            case 'initial_post_time':
                change_config(initial_post_time=value)
                await update.message.reply_text(f'Change config {config_parameter} success.')
            case 'post_frequency':
                change_config(post_frequency=value)
                await update.message.reply_text(f'Change config {config_parameter} success.')
            case 'max_post_per_day':
                change_config(max_post_per_day=value)
                await update.message.reply_text(f'Change config {config_parameter} success.')
            case 'ayat_per_post':
                change_config(ayat_per_post=value)
                await update.message.reply_text(f'Change config {config_parameter} success.')
            case _:
                await update.message.reply_text(error_text)

async def change_quran_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_text = 'Wrong syntax. Proper syntax is:\n\n/change_progress {surah_number} {ayat_number}'
    if len(update.message.text.split()) < 3:
        await update.message.reply_text(error_text)
    else:
        command, surah, ayat = update.message.text.split()
        set_quran_progress(surah, ayat)
        await update.message.reply_text(f'Change Quran progress success.')

async def reset_all_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global INITIAL_POST_TIME
    global POST_FREQUENCY
    global MAX_POST_PER_DAY
    INITIAL_POST_TIME = cp_config.get('QuranPosting', 'InitialPostTime')
    POST_FREQUENCY = cp_config.getint('QuranPosting', 'PostFrequency')
    MAX_POST_PER_DAY = cp_config.getint('QuranPosting', 'MaxPostPerDay')
    remove_all_job(context)
    add_job(context)
    await update.message.reply_text('Job schedules renewed.')

def main() -> None:
    """Run bot."""
    # Create the Application and pass it your bot's token.
    defaults = Defaults(parse_mode=ParseMode.HTML)
    application = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_message))
    application.add_handler(CommandHandler("change_config", change_app_config))
    application.add_handler(CommandHandler("change_progress", change_quran_progress))
    application.add_handler(CommandHandler("show_config", show_current_config))
    application.add_handler(CommandHandler("reset_jobs", reset_all_jobs))

    # create job schedule
    add_job(CallbackContext(application=application))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
