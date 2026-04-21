"""
Localization module for multi-language support
Supports: Uzbek (Latin), Uzbek (Cyrillic), Russian, English
"""

from typing import Dict, Any

# Language codes
LANG_UZ = "uz"        # O'zbekcha (Latin)
LANG_UZ_CYRL = "uz_cyrl"  # Ўзбекча (Cyrillic)
LANG_RU = "ru"        # Русский
LANG_EN = "en"        # English

# Supported languages with display info
LANGUAGES = {
    LANG_UZ: {
        "name": "O'zbekcha",
        "flag": "🇺🇿",
        "native_name": "O'zbekcha"
    },
    LANG_UZ_CYRL: {
        "name": "Ўзбекча",
        "flag": "🇺🇿",
        "native_name": "Ўзбекча"
    },
    LANG_RU: {
        "name": "Русский",
        "flag": "🇷🇺",
        "native_name": "Русский"
    },
    LANG_EN: {
        "name": "English",
        "flag": "🇬🇧",
        "native_name": "English"
    }
}

# All translations
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ============ Language Selection ============
    "choose_language": {
        LANG_UZ: "O'zingizga qulay tilni tanlang 🇺🇿",
        LANG_UZ_CYRL: "Ўзингизга қулай тилни танланг 🇺🇿",
        LANG_RU: "Выбери язык, который тебе нравится 🇷🇺",
        LANG_EN: "Choose the language you like 🇬🇧"
    },
    
    "language_selected": {
        LANG_UZ: "✅ Til o'zgartirildi: O'zbekcha",
        LANG_UZ_CYRL: "✅ Тил ўзгартирилди: Ўзбекча",
        LANG_RU: "✅ Язык изменён: Русский",
        LANG_EN: "✅ Language changed: English"
    },
    
    # ============ Welcome Message ============
    "welcome": {
        LANG_UZ: """👋 Salom, {name}!

🤖 <b>Oxangxbot</b> - ijtimoiy tarmoqlardan video va audio yuklash boti.

📥 <b>Qo'llab-quvvatlanadigan platformalar:</b>
• Instagram - stories, post va reels + audio
• YouTube - videolar va shorts + audio
• TikTok - suv belgisiz video + audio
• Likee - suv belgisiz video + audio
• Pinterest - suv belgisiz video va rasmlar
• Threads - video va rasmlar + audio
• Snapchat - suv belgisiz video + audio

🎵 <b>Shazam funksiyasi:</b>
• Qo'shiq nomi yoki ijrochi ismi
• Qo'shiq matni
• Ovozli xabar, video, audio orqali aniqlash

🎶 <b>Top va qidiruv:</b> <code>/top</code>, <code>/search</code> yoki <code>/s</code>, <code>/shazam</code>, <code>/lyrics</code>.
📱 Buyruqlar ro'yxati: Telegramdagi <b>Menu</b> tugmasi yoki <code>/help</code>.

🚀 <b>Boshlash uchun:</b> media havolasini yuboring yoki yuqoridagi buyruqlardan foydalaning.""",
        
        LANG_UZ_CYRL: """👋 Салом, {name}!

🤖 <b>Oxangxbot</b> - ижтимоий тармоқлардан видео ва аудио юклаш боти.

📥 <b>Қўллаб-қувватланадиган платформалар:</b>
• Instagram - stories, post ва reels + аудио
• YouTube - видеолар ва shorts + аудио
• TikTok - сув белгисиз видео + аудио
• Likee - сув белгисиз видео + аудио
• Pinterest - сув белгисиз видео ва расмлар
• Threads - видео ва расмлар + аудио
• Snapchat - сув белгисиз видео + аудио

🎵 <b>Shazam функцияси:</b>
• Қўшиқ номи ёки ижрочи исми
• Қўшиқ матни
• Овозли хабар, видео, аудио орқали аниқлаш

🎶 <b>Топ ва қидирув:</b> <code>/top</code>, <code>/search</code> ёки <code>/s</code>, <code>/shazam</code>, <code>/lyrics</code>.
📱 Буйруқлар: Telegram <b>Menu</b> тугмаси ёки <code>/help</code>.

🚀 <b>Бошлаш учун:</b> медиа ҳаволасини юборинг ёки буйруқлардан фойдаланинг.""",
        
        LANG_RU: """👋 Привет, {name}!

🤖 <b>Oxangxbot</b> - бот для скачивания видео и аудио из социальных сетей.

📥 <b>Поддерживаемые платформы:</b>
• Instagram - stories, посты и reels + аудио
• YouTube - видео и shorts + аудио
• TikTok - видео без водяного знака + аудио
• Likee - видео без водяного знака + аудио
• Pinterest - видео и изображения без водяного знака
• Threads - видео и изображения + аудио
• Snapchat - видео без водяного знака + аудио

🎵 <b>Функция Shazam:</b>
• Название песни или имя исполнителя
• Текст песни
• Распознавание через голосовое сообщение, видео, аудио

🎶 <b>Топ и поиск:</b> <code>/top</code>, <code>/search</code> или <code>/s</code>, <code>/shazam</code>, <code>/lyrics</code>.
📱 Команды: кнопка <b>Menu</b> в Telegram или <code>/help</code>.

🚀 <b>Для начала:</b> отправьте ссылку на медиа или используйте команды.""",
        
        LANG_EN: """👋 Hello, {name}!

🤖 <b>Oxangxbot</b> - bot for downloading videos and audio from social networks.

📥 <b>Supported platforms:</b>
• Instagram - stories, posts and reels + audio
• YouTube - videos and shorts + audio
• TikTok - watermark-free video + audio
• Likee - watermark-free video + audio
• Pinterest - watermark-free videos and images
• Threads - videos and images + audio
• Snapchat - watermark-free video + audio

🎵 <b>Shazam feature:</b>
• Song title or artist name
• Song lyrics
• Recognition via voice message, video, audio

🎶 <b>Top & search:</b> <code>/top</code>, <code>/search</code> or <code>/s</code>, <code>/shazam</code>, <code>/lyrics</code>.
📱 Commands: Telegram <b>Menu</b> button or <code>/help</code>.

🚀 <b>To start:</b> send a media link or use the commands above."""
    },
    
    "welcome_new_user": {
        LANG_UZ: "\n\n🎉 Xush kelibsiz! Siz yangi foydalanuvchisiz.",
        LANG_UZ_CYRL: "\n\n🎉 Хуш келибсиз! Сиз янги фойдаланувчисиз.",
        LANG_RU: "\n\n🎉 Добро пожаловать! Вы новый пользователь.",
        LANG_EN: "\n\n🎉 Welcome! You are a new user."
    },
    
    # ============ Main Menu ============
    "btn_shazam": {
        LANG_UZ: "🎵 Shazam",
        LANG_UZ_CYRL: "🎵 Shazam",
        LANG_RU: "🎵 Shazam",
        LANG_EN: "🎵 Shazam"
    },
    
    "btn_top_music": {
        LANG_UZ: "🔝 Top musiqalar",
        LANG_UZ_CYRL: "🔝 Топ мусиқалар",
        LANG_RU: "🔝 Топ музыка",
        LANG_EN: "🔝 Top music"
    },
    
    "btn_search_music": {
        LANG_UZ: "🔍 Musiqa qidirish",
        LANG_UZ_CYRL: "🔍 Мусиқа қидириш",
        LANG_RU: "🔍 Поиск музыки",
        LANG_EN: "🔍 Search music"
    },
    
    "btn_statistics": {
        LANG_UZ: "📊 Statistika",
        LANG_UZ_CYRL: "📊 Статистика",
        LANG_RU: "📊 Статистика",
        LANG_EN: "📊 Statistics"
    },
    
    "btn_help": {
        LANG_UZ: "ℹ️ Yordam",
        LANG_UZ_CYRL: "ℹ️ Ёрдам",
        LANG_RU: "ℹ️ Помощь",
        LANG_EN: "ℹ️ Help"
    },
    
    "btn_settings": {
        LANG_UZ: "⚙️ Sozlamalar",
        LANG_UZ_CYRL: "⚙️ Созламалар",
        LANG_RU: "⚙️ Настройки",
        LANG_EN: "⚙️ Settings"
    },
    
    "btn_language": {
        LANG_UZ: "🌐 Tilni o'zgartirish",
        LANG_UZ_CYRL: "🌐 Тилни ўзгартириш",
        LANG_RU: "🌐 Изменить язык",
        LANG_EN: "🌐 Change language"
    },
    
    "btn_cancel": {
        LANG_UZ: "❌ Bekor qilish",
        LANG_UZ_CYRL: "❌ Бекор қилиш",
        LANG_RU: "❌ Отмена",
        LANG_EN: "❌ Cancel"
    },

    "cancel_done": {
        LANG_UZ: "✅ Bekor qilindi. Davom etish uchun <code>/help</code> yoki menyudagi buyruqlardan foydalaning.",
        LANG_UZ_CYRL: "✅ Бекор қилинди. Давом этиш учун <code>/help</code> ёки менюдаги буйруқлардан фойдаланинг.",
        LANG_RU: "✅ Отменено. Продолжите через <code>/help</code> или команды в меню.",
        LANG_EN: "✅ Cancelled. Use <code>/help</code> or the commands in the menu to continue.",
    },
    
    "btn_back": {
        LANG_UZ: "⬅️ Orqaga",
        LANG_UZ_CYRL: "⬅️ Орқага",
        LANG_RU: "⬅️ Назад",
        LANG_EN: "⬅️ Back"
    },
    
    # ============ Help ============
    "help": {
        LANG_UZ: """📖 <b>Yordam</b>

<b>Media yuklash:</b>
• Shunchaki Instagram, YouTube, TikTok va boshqa platformalardan havola yuboring
• Bot avtomatik platformani aniqlab, medialni yuklaydi

<b>YouTube uchun:</b>
• Video sifatini tanlash imkoniyati (1080p, 720p, 480p, 360p)
• MP3 formatida audio yuklash

<b>Musiqa buyruqlari:</b>
/shazam - Qo'shiq aniqlash (Shazam)
/search &lt;nomi&gt; - Musiqa qidirish
/top - Top musiqalar (Shazam)
/lyrics &lt;shazam_id&gt; - Qo'shiq matni

<b>Asosiy buyruqlar:</b>
/start - Botni qayta ishga tushirish
/help - Yordam
/stats - Statistika
/settings - Sozlamalar (til — /language)
/language - Tilni o'zgartirish
/cancel - Joriy qadamni bekor qilish""",
        
        LANG_UZ_CYRL: """📖 <b>Ёрдам</b>

<b>Медиа юклаш:</b>
• Шунчаки Instagram, YouTube, TikTok ва бошқа платформалардан ҳавола юборинг
• Бот автоматик платформани аниқлаб, медиани юклайди

<b>YouTube учун:</b>
• Видео сифатини танлаш имконияти (1080p, 720p, 480p, 360p)
• MP3 форматида аудио юклаш

<b>Мусиқа буйруқлари:</b>
/shazam - Қўшиқ аниқлаш (Shazam)
/search &lt;номи&gt; - Мусиқа қидириш
/top - Топ мусиқалар (Shazam)
/lyrics &lt;shazam_id&gt; - Қўшиқ матни

<b>Асосий буйруқлар:</b>
/start - Ботни қайта ишга тушириш
/help - Ёрдам
/stats - Статистика
/settings - Созламалар (тил — /language)
/language - Тилни ўзгартириш
/cancel - Жорий қадамни бекор қилиш""",
        
        LANG_RU: """📖 <b>Помощь</b>

<b>Скачивание медиа:</b>
• Просто отправьте ссылку из Instagram, YouTube, TikTok и других платформ
• Бот автоматически определит платформу и скачает медиа

<b>Для YouTube:</b>
• Выбор качества видео (1080p, 720p, 480p, 360p)
• Скачивание аудио в формате MP3

<b>Музыкальные команды:</b>
/shazam - Распознать музыку (Shazam)
/search &lt;название&gt; - Поиск музыки
/top - Топ музыка (Shazam)
/lyrics &lt;shazam_id&gt; - Текст песни

<b>Основные команды:</b>
/start - Перезапустить бота
/help - Помощь
/stats - Статистика
/settings - Настройки (язык — /language)
/language - Изменить язык
/cancel - Отменить текущий шаг""",
        
        LANG_EN: """📖 <b>Help</b>

<b>Downloading media:</b>
• Just send a link from Instagram, YouTube, TikTok and other platforms
• Bot will automatically detect the platform and download media

<b>For YouTube:</b>
• Choose video quality (1080p, 720p, 480p, 360p)
• Download audio in MP3 format

<b>Music commands:</b>
/shazam - Recognize music (Shazam)
/search &lt;name&gt; - Search music
/top - Top music (Shazam)
/lyrics &lt;shazam_id&gt; - Song lyrics

<b>Main commands:</b>
/start - Restart the bot
/help - Help
/stats - Statistics
/settings - Settings (language — /language)
/language - Change language
/cancel - Cancel current step"""
    },
    
    # ============ Statistics ============
    "statistics": {
        LANG_UZ: """📊 <b>Statistika</b>

<b>Sizning statistikangiz:</b>
• 📥 Yuklanganlar: {user_downloads}
• 📅 Ro'yxatdan o'tish: {registered_date}

<b>Umumiy statistika:</b>
• 👥 Jami foydalanuvchilar: {total_users}
• 🟢 Faol (7 kun): {active_users}
• 📥 Jami yuklanganlar: {total_downloads}""",
        
        LANG_UZ_CYRL: """📊 <b>Статистика</b>

<b>Сизнинг статистикангиз:</b>
• 📥 Юкланганлар: {user_downloads}
• 📅 Рўйхатдан ўтиш: {registered_date}

<b>Умумий статистика:</b>
• 👥 Жами фойдаланувчилар: {total_users}
• 🟢 Фаол (7 кун): {active_users}
• 📥 Жами юкланганлар: {total_downloads}""",
        
        LANG_RU: """📊 <b>Статистика</b>

<b>Ваша статистика:</b>
• 📥 Скачиваний: {user_downloads}
• 📅 Дата регистрации: {registered_date}

<b>Общая статистика:</b>
• 👥 Всего пользователей: {total_users}
• 🟢 Активных (7 дней): {active_users}
• 📥 Всего скачиваний: {total_downloads}""",
        
        LANG_EN: """📊 <b>Statistics</b>

<b>Your statistics:</b>
• 📥 Downloads: {user_downloads}
• 📅 Registration date: {registered_date}

<b>Overall statistics:</b>
• 👥 Total users: {total_users}
• 🟢 Active (7 days): {active_users}
• 📥 Total downloads: {total_downloads}"""
    },
    
    # ============ Download Messages ============
    "downloading": {
        LANG_UZ: "⏳ Yuklanmoqda...",
        LANG_UZ_CYRL: "⏳ Юкланмоқда...",
        LANG_RU: "⏳ Загрузка...",
        LANG_EN: "⏳ Downloading..."
    },
    
    "processing": {
        LANG_UZ: "🔄 Qayta ishlanmoqda...",
        LANG_UZ_CYRL: "🔄 Қайта ишланмоқда...",
        LANG_RU: "🔄 Обработка...",
        LANG_EN: "🔄 Processing..."
    },
    
    "download_success": {
        LANG_UZ: "✅ Muvaffaqiyatli yuklandi!",
        LANG_UZ_CYRL: "✅ Муваффақиятли юкланди!",
        LANG_RU: "✅ Успешно загружено!",
        LANG_EN: "✅ Successfully downloaded!"
    },
    
    "download_error": {
        LANG_UZ: "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
        LANG_UZ_CYRL: "❌ Хатолик юз берди. Илтимос, қайтадан уриниб кўринг.",
        LANG_RU: "❌ Произошла ошибка. Пожалуйста, попробуйте снова.",
        LANG_EN: "❌ An error occurred. Please try again."
    },

    "media_download_failed_ig": {
        LANG_UZ: (
            "❌ Instagram videoni yuborib bo‘lmadi (CDN 403).\n\n"
            "<b>Serverda:</b> <code>pip install yt-dlp</code> — bot avvalo CDN, ishlamasa <code>yt-dlp</code> bilan yuklaydi.\n"
            "Yoki <code>HTTPS_PROXY</code> / rezident proxy ni <code>.env</code> ga qo‘shing."
        ),
        LANG_UZ_CYRL: (
            "❌ Instagram видеони юбориб бўлмади (CDN 403).\n\n"
            "<b>Серверда:</b> <code>pip install yt-dlp</code> — бот аввало CDN, ишламаса <code>yt-dlp</code> билан юклайди.\n"
            "Ёки <code>HTTPS_PROXY</code> / резидент проксини <code>.env</code> га қўшинг."
        ),
        LANG_RU: (
            "❌ Не удалось отправить Instagram (CDN 403).\n\n"
            "<b>На сервере:</b> <code>pip install yt-dlp</code> — сначала CDN, иначе загрузка через <code>yt-dlp</code>.\n"
            "Или добавьте <code>HTTPS_PROXY</code> / резидентный прокси в <code>.env</code>."
        ),
        LANG_EN: (
            "❌ Could not send Instagram media (CDN 403).\n\n"
            "<b>On the server:</b> <code>pip install yt-dlp</code> — bot tries CDN first, then <code>yt-dlp</code>.\n"
            "Or set <code>HTTPS_PROXY</code> / residential proxy in <code>.env</code>."
        ),
    },
    
    "unsupported_url": {
        LANG_UZ: "❌ Bu havola qo'llab-quvvatlanmaydi.",
        LANG_UZ_CYRL: "❌ Бу ҳавола қўллаб-қувватланмайди.",
        LANG_RU: "❌ Эта ссылка не поддерживается.",
        LANG_EN: "❌ This link is not supported."
    },
    
    "choose_quality": {
        LANG_UZ: "📹 Video sifatini tanlang:",
        LANG_UZ_CYRL: "📹 Видео сифатини танланг:",
        LANG_RU: "📹 Выберите качество видео:",
        LANG_EN: "📹 Choose video quality:"
    },
    
    "extract_audio": {
        LANG_UZ: "🎵 Audio yuklash",
        LANG_UZ_CYRL: "🎵 Аудио юклаш",
        LANG_RU: "🎵 Скачать аудио",
        LANG_EN: "🎵 Download audio"
    },
    
    # ============ Shazam ============
    "shazam_send_audio": {
        LANG_UZ: "🎵 Musiqa uchun video, audio yoki ovozli xabar yuboring.\nBekor: <code>/cancel</code>",
        LANG_UZ_CYRL: "🎵 Мусиқа учун видео, аудио ёки овозли хабар юборинг.\nБекор: <code>/cancel</code>",
        LANG_RU: "🎵 Отправьте видео, аудио или голосовое для распознавания.\nОтмена: <code>/cancel</code>",
        LANG_EN: "🎵 Send video, audio or voice for recognition.\nCancel: <code>/cancel</code>"
    },
    
    "shazam_analyzing": {
        LANG_UZ: "🎵 Musiqa aniqlanmoqda...",
        LANG_UZ_CYRL: "🎵 Мусиқа аниқланмоқда...",
        LANG_RU: "🎵 Распознавание музыки...",
        LANG_EN: "🎵 Recognizing music..."
    },
    
    "shazam_not_found": {
        LANG_UZ: "❌ Musiqa aniqlanmadi. Boshqa audio yuboring.",
        LANG_UZ_CYRL: "❌ Мусиқа аниқланмади. Бошқа аудио юборинг.",
        LANG_RU: "❌ Музыка не распознана. Отправьте другое аудио.",
        LANG_EN: "❌ Music not recognized. Send another audio."
    },
    
    # ============ Search ============
    "search_enter_query": {
        LANG_UZ: "🔍 Qo'shiq nomi yoki ijrochi ismini yozing.\nBekor qilish: <code>/cancel</code>",
        LANG_UZ_CYRL: "🔍 Қўшиқ номи ёки ижрочи исмини ёзинг.\nБекор қилиш: <code>/cancel</code>",
        LANG_RU: "🔍 Введите название песни или имя исполнителя.\nОтмена: <code>/cancel</code>",
        LANG_EN: "🔍 Type the song or artist name.\nCancel: <code>/cancel</code>"
    },
    
    "search_no_results": {
        LANG_UZ: "❌ Hech narsa topilmadi.",
        LANG_UZ_CYRL: "❌ Ҳеч нарса топилмади.",
        LANG_RU: "❌ Ничего не найдено.",
        LANG_EN: "❌ Nothing found."
    },
    
    "search_results": {
        LANG_UZ: "🎵 Qidiruv natijalari:",
        LANG_UZ_CYRL: "🎵 Қидирув натижалари:",
        LANG_RU: "🎵 Результаты поиска:",
        LANG_EN: "🎵 Search results:"
    },
    
    # ============ Settings ============
    "settings": {
        LANG_UZ: "⚙️ <b>Sozlamalar</b>\n\nTilni o'zgartirish uchun tugmani bosing:",
        LANG_UZ_CYRL: "⚙️ <b>Созламалар</b>\n\nТилни ўзгартириш учун тугмани босинг:",
        LANG_RU: "⚙️ <b>Настройки</b>\n\nНажмите кнопку чтобы изменить язык:",
        LANG_EN: "⚙️ <b>Settings</b>\n\nPress the button to change language:"
    },
    
    # ============ Errors ============
    "banned": {
        LANG_UZ: "❌ Siz bloklangansiz!",
        LANG_UZ_CYRL: "❌ Сиз блокланганнсиз!",
        LANG_RU: "❌ Вы заблокированы!",
        LANG_EN: "❌ You are blocked!"
    },
    
    "wait": {
        LANG_UZ: "⏳ Iltimos, biroz kuting...",
        LANG_UZ_CYRL: "⏳ Илтимос, бироз кутинг...",
        LANG_RU: "⏳ Пожалуйста, подождите...",
        LANG_EN: "⏳ Please wait..."
    },
    
    "error": {
        LANG_UZ: "❌ Xatolik yuz berdi!",
        LANG_UZ_CYRL: "❌ Хатолик юз берди!",
        LANG_RU: "❌ Произошла ошибка!",
        LANG_EN: "❌ An error occurred!"
    },

    "downloaded_via": {
        LANG_UZ: "📥 @{bot_username} orqali yuklab olindi",
        LANG_UZ_CYRL: "📥 @{bot_username} орқали юклаб олинди",
        LANG_RU: "📥 Скачано через @{bot_username}",
        LANG_EN: "📥 Downloaded via @{bot_username}"
    },
    
    "btn_download_audio": {
        LANG_UZ: "📥 Qo'shiqni yuklab olish",
        LANG_UZ_CYRL: "📥 Қўшиқни юклаб олиш",
        LANG_RU: "📥 Скачать песню",
        LANG_EN: "📥 Download song"
    },
    
    "btn_share": {
        LANG_UZ: "↗️ Do'stlarga ulashish",
        LANG_UZ_CYRL: "↗️ Дўстларга улашиш",
        LANG_RU: "↗️ Поделиться с друзьями",
        LANG_EN: "↗️ Share with friends"
    },
    
    # ============ Voice Commands ============
    "voice_processing": {
        LANG_UZ: "🎤 Ovozli xabar qayta ishlanmoqda...",
        LANG_UZ_CYRL: "🎤 Овозли хабар қайта ишланмоқда...",
        LANG_RU: "🎤 Обработка голосового сообщения...",
        LANG_EN: "🎤 Processing voice message..."
    },
    
    "voice_recognized": {
        LANG_UZ: "🎤 Aniqlandi: <i>{text}</i>\n\n🔍 Qidirilmoqda: <b>{query}</b>",
        LANG_UZ_CYRL: "🎤 Аниқланди: <i>{text}</i>\n\n🔍 Қидирилмоқда: <b>{query}</b>",
        LANG_RU: "🎤 Распознано: <i>{text}</i>\n\n🔍 Поиск: <b>{query}</b>",
        LANG_EN: "🎤 Recognized: <i>{text}</i>\n\n🔍 Searching: <b>{query}</b>"
    },
    
    "voice_not_recognized": {
        LANG_UZ: "❌ Ovozli xabar aniqlanmadi. Qaytadan urinib ko'ring.",
        LANG_UZ_CYRL: "❌ Овозли хабар аниқланмади. Қайтадан уриниб кўринг.",
        LANG_RU: "❌ Голосовое сообщение не распознано. Попробуйте снова.",
        LANG_EN: "❌ Voice message not recognized. Please try again."
    },
    
    "voice_disabled": {
        LANG_UZ: "❌ Ovozli buyruqlar hozircha mavjud emas.",
        LANG_UZ_CYRL: "❌ Овозли буйруқлар ҳозирча мавжуд эмас.",
        LANG_RU: "❌ Голосовые команды временно недоступны.",
        LANG_EN: "❌ Voice commands are currently unavailable."
    }
}


def get_text(key: str, lang: str = LANG_UZ, **kwargs) -> str:
    """
    Get translated text by key and language code
    
    Args:
        key: Translation key
        lang: Language code (uz, uz_cyrl, ru, en)
        **kwargs: Format parameters for the text
    
    Returns:
        Translated and formatted text
    """
    if key not in TRANSLATIONS:
        return key
    
    translations = TRANSLATIONS[key]
    
    # Fallback to Uzbek if language not found
    if lang not in translations:
        lang = LANG_UZ
    
    text = translations.get(lang, translations.get(LANG_UZ, key))
    
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    
    return text


def get_language_name(lang_code: str) -> str:
    """Get human-readable language name"""
    if lang_code in LANGUAGES:
        return f"{LANGUAGES[lang_code]['flag']} {LANGUAGES[lang_code]['native_name']}"
    return lang_code


def normalize_language_code(lang_code: str) -> str:
    """
    Normalize language code from Telegram or database
    Maps various formats to our standard codes
    """
    if not lang_code:
        return LANG_UZ
    
    lang_code = lang_code.lower().strip()
    
    # Direct matches
    if lang_code in (LANG_UZ, LANG_UZ_CYRL, LANG_RU, LANG_EN):
        return lang_code
    
    # Map common variations
    mapping = {
        "uz-latn": LANG_UZ,
        "uz-cyrl": LANG_UZ_CYRL, 
        "uzb": LANG_UZ,
        "ru-ru": LANG_RU,
        "rus": LANG_RU,
        "en-us": LANG_EN,
        "en-gb": LANG_EN,
        "eng": LANG_EN,
    }
    
    return mapping.get(lang_code, LANG_UZ)
