"""All user-facing message strings for the Assignment Notifier bot."""

# ── Welcome & Help ────────────────────────────────────────────────────────────

WELCOME = (
    "*USAS Assignment Notifier*\n\n"
    "I’ll notify you when a *new assignment* appears on your LMS so you don’t have to check. Stay on top of everything!\n\n"
    "👇 Tap *Register* below or /register to start."
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
    "I securely connect to your USAS LMS using your credentials to monitor for updates.\n\n"
    "Every hour, my system runs an automated check (a heartbeat scan) across all your courses. It looks for new assignments, quizzes, or task updates that you haven't been notified about yet.\n\n"
    "When a change is detected, I immediately generate a notification bubble and send it to your chat here.\n\n"
    "*Example*:\n"
    "Think of it like a scheduled bus. If the bot is set to scan every hour at :00, and your lecturer uploads a task at 10:20 PM, the bot will pick it up at the next scheduled scan at 11:00 PM. This ensures you are always kept in the loop without having to manually refresh the LMS.\n\n"
    "Contact @STEMUSAS for support."
)

# ── Registration Flow ─────────────────────────────────────────────────────────

PROMPT_MEMBERSHIP_ID = (
    "Step 1/3\n\n"
    "Please enter your *STEM ID*:\n"
    "(Example: `STEM(25/26)0016`)\n\n"
    "Get it in @stemusasbot"
)

PROMPT_STUDENT_ID = (
    "ID: `{membership_id}`\n\n"
    "Step 2/3\n"
    "Please type your *Matric Number*:\n"
    "(Example: `I24067510`)"
)

PROMPT_PASSWORD = (
    "ID: `{membership_id}`\n"
    "Matric: `{student_id}`\n\n"
    "Step 3/3\n"
    "Please enter your *LMS Password*:"
)

# -- Errors & Validation -------------------------------------------------------

ERR_MEMBERSHIP_NOT_FOUND = (
    "*❌ Membership Not Found*\n\n"
    "I couldn't find that *ID* in our records. Please ensure you have joined *STEM* to use this bot.\n\n"
    "Contact @STEMUSAS if you think this is an error."
)

ERR_MEMBERSHIP_MATRIC_MISMATCH = (
    "*❌ Matric Mismatch*\n\n"
    "The *Matric ID* you entered (*{entered}*) does *not match* our records for this membership.\n\n"
    "Please *try again* or contact @STEMUSAS."
)

REGISTERED_OK = "*✅ Registration successful*, *{name}*!\n\nI'm now *monitoring* your *assignments*. Happy studying! 🚀"

ALREADY_REGISTERED = "*Welcome back*, *{name}*!\n\n*Everything’s up to date*. I’ll keep an eye on your *assignments* for you 😉"

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
    "<b>{days} day(s) before deadline</b>\n"
    "<i>{quote}</i>"
)

COUNTDOWN_QUOTES_3D = [
    "Weh bangun. Sekarang. Bukan nanti. SEKARANG.",
    "Kau dah tak ada masa nak fikir. Terus buat.",
    "Perfect buang jauh. SIAP itu target.",
    "Kalau kau tak start dalam 5 minit ni, kau sendiri pilih untuk fail.",
    "Stop scroll. Letak phone. Buka laptop. Buat kerja.",
    "Jangan tunggu mood. Mood takkan datang. Kau kena paksa.",
    "Buat yang paling penting dulu. Yang lain kalau sempat baru tambah.",
    "Tak payah cantik. Janji cukup syarat dan boleh submit.",
    "Kau ada maybe 10 sampai 15 jam je betul-betul produktif. Guna.",
    "Kalau kau tangguh lagi sekarang, memang habis.",
]

COUNTDOWN_QUOTES_2D = [
    "Dengar sini. Kau dah hampir habis masa. Start sekarang atau memang bye.",
    "Jangan duduk lagi. Buka laptop. Buat kerja. Sekarang.",
    "Tak ada 'kejap lagi'. Itu ayat orang gagal.",
    "Kau nak lulus atau nak bagi alasan? Pilih sekarang.",
    "Perfect tu untuk orang yang start awal. Kau tak layak fikir tu dah.",
    "Set timer 30 minit. Buat tanpa berhenti. Ulang sampai siap.",
    "Kalau kau buka phone lagi, memang kau sabotage diri sendiri.",
    "Tak payah fikir susah ke senang. Kau buat je sampai siap.",
    "Ini bukan pasal rajin. Ini pasal kau nak selamat atau tak.",
    "Kalau kau tak siap, itu bukan sebab susah. Itu sebab kau tak buat.",
]

COUNTDOWN_QUOTES_1D = [
    "KAU BUAT APA LAGI NI?? DEADLINE ESOK.",
    "STOP SEMUA BENDA. BUKA LAPTOP. BUAT KERJA SEKARANG.",
    "TAK PAYAH BAGI ALASAN. TAK ADA SIAPA NAK DENGAR.",
    "KAU NAK LULUS KE TAK? SIMPLE JE SOALAN TU.",
    "JANGAN TUNGGU MOOD. MOOD TAKKAN DATANG.",
    "PERFECT? LUPA. SIAPKAN DULU BARU CERITA.",
    "SET TIMER. DUDUK. BUAT. JANGAN BERHENTI.",
    "PHONE TU LETAK JAUH. KALAU TAK, MEMANG KAU YANG ROSAKKAN DIRI SENDIRI.",
    "KAU ADA SATU HARI JE. JANGAN BUANG LAGI MASA.",
    "KALAU KAU MASIH TAK START SEKARANG, MEMANG KAU YANG PILIH UNTUK FAIL.",
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
ASSIGNMENT_LINK_LINE = "🔗 <a href=\"{link}\">Link</a>"

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


# ── Rate Limiting ───────────────────────────────────────────────────────────

RATE_LIMIT_USER = "⏳ *Please wait!* You can check again in *{remaining}*.\n\nTo prevent server blocks, manual checks are limited to once every 5 minutes."
RATE_LIMIT_ADMIN = "⏳ *Cooling down...*\n\nThe global poll was recently triggered. Please wait *{remaining}* before triggering it again."

# ── Generic ───────────────────────────────────────────────────────────────────

SOMETHING_WENT_WRONG = "*⚠️ Something went wrong.* Please try again later."
