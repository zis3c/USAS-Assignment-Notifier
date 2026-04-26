"""All user-facing message strings for the Assignment Notifier bot."""

# ── Welcome & Help ────────────────────────────────────────────────────────────

WELCOME = (
    "*USAS Assignment Notifier*\n\n"
    "I’ll notify you when a *new assignment* appears on your LMS so you don’t have to check. Stay on top of everything!\n\n"
    "👇 Tap *Register* or /register."
)

HELP = (
    "*About This Bot*\n\n"
    "This service monitors the *USAS LMS* for *new assignments* and notifies you *instantly*.\n\n"
    "*Register* - Link LMS account\n"
    "*Check Now* - Scan tasks now\n"
    "*Status* - View account info\n"
    "*Logout* - Remove your data\n\n"
    "Made by *zis3c* 🔥"
)
 
HELP_DETAIL = (
    "*How it works?*\n\n"
    "After you register, I check your USAS LMS automatically every hour, and if I find a new assignment, quiz, or deadline update, I send it to you right away.\n\n"
    "I also send reminder messages when your assignment is 3 days, 2 days, and within 24 hours before the deadline, and you can tap *Check Now* anytime for an instant scan.\n\n"
    "If you face any problems, please contact the project maintainer."
)

# ── Registration Flow ─────────────────────────────────────────────────────────

PROMPT_STUDENT_ID = (
    "Step 1/2\n\n"
    "Please type your *Matric Number*:\n"
    "(Example: `I24067510`)"
)

PROMPT_PASSWORD = (
    "Matric: `{student_id}`\n\n"
    "Step 2/2\n"
    "Please enter your *LMS Password*:"
)

# -- Errors & Validation -------------------------------------------------------

REGISTERED_OK = "*Registration successful*, *{name}*!\n\nI'm now *monitoring* your *assignments*. Happy studying!"

ALREADY_REGISTERED = "*Welcome back*, *{name}*!\n\n*Everything is up to date.* I will check your LMS every *1 hour* and keep an eye on your *assignments* for you."

LOGIN_FAILED = (
    "*❌ Login Failed*\n\n"
    "I couldn't *sign in* to your *LMS*. Please double-check your *Matric ID* and *Password*."
)

REGISTER_CANCELLED = (
    "*❌ Registration Cancelled*\n\n"
    "No changes were *saved*. Use the *menu* to start over."
)

# -- Logout --------------------------------------------------------------------

UNREGISTER_CONFIRM = (
    "*Logout* (*{matric}*)?\n\n"
    "This *stops notifications* and *removes* your data."
)

UNREGISTERED_OK = (
    "*Logged out successfully.*\n\n"
    "All data *removed*. You will no longer receive *notifications*."
)

NOT_REGISTERED = (
    "*You are not registered.*\n\n"
    "Use *Register* in the menu to start."
)

UNREGISTER_CANCELLED = (
    "*Logout Cancelled*\n\n"
    "No changes made. You are still *securely bound*."
)

# ── Status ────────────────────────────────────────────────────────────────────

STATUS_OK = (
    "*Account Status*\n\n"
    "Name: *{lms_name}*\n"
    "Matric: *{matric}*\n"
    "Last scan: *{last_checked}*\n"
    "Timezone: *{tz}*"
)

STATUS_NEVER_CHECKED = (
    "*Account Status*\n\n"
    "Name: *{lms_name}*\n"
    "Matric: *{matric}*\n"
    "Last scan: *Pending*\n"
    "Timezone: *Asia/Kuala_Lumpur*"
)

# ── Manual Check ──────────────────────────────────────────────────────────────

CHECK_RUNNING = (
    "*🔎 Scan Started*\n\n"
    "Checking *LMS* now... please wait."
)

CHECK_NO_NEW = (
    "*✅ All caught up!*\n\n"
    "*No* new *assignments* found since your last check."
)

CHECK_NEW = (
    "*📬 Done!* Found *{count}* new assignment(s).\n"
    "Check the notifications above. 👆"
)

CHECK_PENDING_ONLY = (
    "*📌 Pending assignments*\n\n"
    "You still have *{count}* pending assignment(s)."
)

CHECK_TEMP_ERROR = (
    "*⚠️ LMS check failed.*\n\n"
    "I couldn't read your LMS right now. Please try again in a moment."
)

COUNTDOWN_REMINDER_HEADER = (
    "📌 <b>Pending Assignment Reminder</b>\n\n"
    "<b>{days_text} before deadline</b>\n"
    "<i>{quote}</i>"
)

COUNTDOWN_QUOTES_3D = [
    "Okay masih sempat. Tapi kalau kau tak start hari ni, esok memang sakit.",
    "Start kecil pun takpe. Janji start dulu sekarang.",
    "Jangan tunggu free time. Kau memang takkan rasa free.",
    "Buka je dulu assignment tu. Faham sikit pun dah cukup.",
    "Buat sikit hari ni, kau akan selamat nanti.",
    "Tak payah fikir siap. Fikir mula dulu.",
    "Kalau kau start sekarang, kau masih ada control.",
    "3 hari nampak lama. Tapi sebenarnya cepat gila habis.",
    "Satu jam sekarang lebih bernilai dari 5 jam last minute.",
    "Jangan aim perfect. Aim progress dulu.",
]

COUNTDOWN_QUOTES_2D = [
    "Dah tak banyak masa. Apa pun jadi, kau kena start sekarang.",
    "Kalau kau masih tak mula, itu memang bahaya dah.",
    "Tak ada lagi try slow-slow. Kau kena push sekarang.",
    "Kau bukan tak boleh. Kau je tak buat lagi.",
    "Buka laptop. Buat walaupun malas. Itu je jalan.",
    "Kalau kau tangguh lagi, esok kau akan menyesal gila.",
    "Tak payah tunggu faham semua. Buat dulu.",
    "2 hari ni menentukan kau lulus atau tak.",
    "Stop fikir. Start buat.",
    "Ini last chance untuk kau buat dengan tenang sikit.",
]

COUNTDOWN_QUOTES_1D = [
    "24 JAM JE TINGGAL. KAU BUAT APA LAGI DUDUK DIAM?",
    "MASA TENGAH LARI, KAU BOLEH LAGI BUAT TAK KISAH?",
    "STOP SCROLL. BENDA TU TAK AKAN SIAP SENDIRI.",
    "KAU NAK FAIL KE? SEBAB ITU JE YANG KAU TUNJUK SEKARANG.",
    "JANGAN BAGI ALASAN BODOH. BUKA KERJA TU SEKARANG.",
    "KAU INGAT ADA MASA LAGI? TAK ADA. DAH TERLAMBAT DAH.",
    "DUDUK. DIAM. BUAT KERJA. SIMPLE JE.",
    "MOOD TAK MOOD, KAU KENA BUAT JUGA. FAHAM?",
    "KAU NAK MENYESAL ESOK? TERUSKAN BUANG MASA SEKARANG.",
    "TAK PAYAH DRAMA. KAU JE YANG TAK START LAGI.",
    "CLICK FAIL TU SEKARANG. TAK PAYAH FIKIR PANJANG.",
    "SET TIMER DAN IKUT. JANGAN DEGIL.",
    "KAU MALAS ATAU KAU TAKUT? APA-APA PUN, BUAT.",
    "SETIAP MINIT KAU LENGAH, KAU ROSAKKAN PELUANG SENDIRI.",
    "JANGAN HARAP MIRACLE. TAK ADA BENDA TU.",
    "KAU NAK SENANG? BUAT SEKARANG. KALAU TAK, PADAN MUKA.",
    "STOP LARI. HADAP KERJA TU SEKARANG.",
    "INI BUKAN LAWAK. DEADLINE DAH DEKAT GILA.",
    "KAU ADA MASA SEKARANG JE. LEPAS NI, SIAP.",
    "KALAU KAU MASIH TAK START, MEMANG KAU YANG PILIH UNTUK FAIL.",
]

# ── Assignment Notification Card ──────────────────────────────────────────────

NEW_ASSIGNMENT_HEADER = "📚 <b>New Assignment</b>"
PENDING_ASSIGNMENT_HEADER = "📌 <b>Pending Assignment Reminder</b>"
ASSIGNMENT_ITEM = (
    "{subject_line}"
    "Title: <b>{title}</b>\n"
    "{due_line}"
    "{link_line}"
)

ASSIGNMENT_SUBJECT_LINE = "Subject: <b>{subject}</b>\n"
ASSIGNMENT_DUE_LINE = "Due: <b>{due}</b>\n"
ASSIGNMENT_LINK_LINE = "Link: <a href=\"{link}\">Assignment</a>"

# ── Admin Dashboard ───────────────────────────────────────────────────────────

ADMIN_WELCOME = (
    "*Admin Dashboard*\n\n"
    "Welcome back, *Admin*. Choose a management tool below."
)

ADMIN_STATS = (
    "*User Statistics*\n\n"
    "Total Active Users: *{total}*\n"
    "Total Registered: *{registered}*"
)

ADMIN_USER_LIST_HEADER = "*Registered Users (Matric : Chat ID)*\n\n"
ADMIN_USER_LINE = "{index}. `{matric}` : `{chat_id}`\n"

ADMIN_POLL_STARTED = "*🔄 Poll Triggered*\n\nBackground check for all users has started."

# ── Advanced Admin Tools ───────────────────────────────────────────────────

ADMIN_FIND_USER_PROMPT = "*🔍 Find User*\n\nPlease enter the *Matric ID* you want to search for:"
ADMIN_USER_NOT_FOUND = "*❌ User not found.*"
ADMIN_USER_DETAILS = (
    "*👤 User Details*\n\n"
    "Matric: `{matric}`\n"
    "Chat ID: `{chat_id}`\n"
    "Status: *{status}*\n"
    "Created: *{created}*\n"
    "Banned: *{banned}*"
)

ADMIN_BROADCAST_PROMPT = "*📢 Broadcast Message*\n\nType the message you want to send to *everyone*:"
ADMIN_BROADCAST_PREVIEW = (
    "*📝 Preview:*\n\n"
    "{message}\n\n"
    "*Send this to {count} users?*"
)
ADMIN_BROADCAST_SUCCESS = "*✅ Broadcast sent!*"

ADMIN_MAINTENANCE_TOGGLE = "*Maintenance Mode*\n\nStatus: *{status}*\n\nWhen active, regular users cannot use the bot."
ADMIN_MAINTENANCE_ACTIVE_MSG = "*🚧 System Maintenance*\n\nThe bot is currently undergoing updates. Please check back later!"

ADMIN_BAN_SUCCESS = "*🚫 User {matric} has been banned.*"
ADMIN_UNBAN_SUCCESS = "*✅ User {matric} has been unbanned.*"

ADMIN_PERFORMANCE = (
    "*🖥️ Server Performance*\n\n"
    "CPU Usage: *{cpu}%*\n"
    "RAM Usage: *{ram_used} GB / {ram_total} GB ({ram_percent}%)*\n"
    "Disk Usage: *{disk_used} GB / {disk_total} GB ({disk_percent}%)*\n"
    "Uptime: *{uptime}*"
)



ADMIN_HEALTH = (
    "*Polling Health*\n\n"
    "Last successful poll: *{last_successful_poll}*\n"
    "LMS fail streak: *{fail_streak}*\n"
    "Active users: *{active_users}*"
)

# ── Rate Limiting ───────────────────────────────────────────────────────────

RATE_LIMIT_USER = "⏳ *Please wait!* You can check again in *{remaining}*.\n\nTo prevent server blocks, manual checks are limited to once every 5 minutes."
RATE_LIMIT_ADMIN = "⏳ *Cooling down...*\n\nThe global poll was recently triggered. Please wait *{remaining}* before triggering it again."

# ── Generic ───────────────────────────────────────────────────────────────────

SOMETHING_WENT_WRONG = "*⚠️ Something went wrong.* Please try again later."


