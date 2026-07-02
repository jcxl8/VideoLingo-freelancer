import os,sys
import glob
import re
import subprocess
import ssl
import shutil
import tempfile
from core.utils import *

def sanitize_filename(filename):
    # Remove or replace illegal characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Ensure filename doesn't start or end with a dot or space
    filename = filename.strip('. ')
    # Use default name if filename is empty
    return filename if filename else 'video'

def update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        if 'yt_dlp' in sys.modules:
            del sys.modules['yt_dlp']
        rprint("[green]yt-dlp updated[/green]")
    except subprocess.CalledProcessError as e:
        rprint(f"[yellow]Warning: Failed to update yt-dlp: {e}[/yellow]")
    from yt_dlp import YoutubeDL
    return YoutubeDL

def _is_certificate_error(error):
    err_text = str(error).lower()
    return (
        "certificate_verify_failed" in err_text
        or "certificate verify failed" in err_text
        or "unable to get local issuer certificate" in err_text
        or isinstance(error, ssl.SSLError)
    )

def _download_with_ytdlp(YoutubeDL, ydl_opts, url):
    """Download video and return the info dict (includes description)."""
    try:
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)
    except Exception as e:
        if not _is_certificate_error(e):
            err_msg = str(e)
            if "sign in to confirm your age" in err_msg.lower() or "confirm your age" in err_msg.lower():
                raise RuntimeError(
                    "YouTube requires age verification for this video.\n"
                    "Please set up YouTube cookies:\n"
                    "1. Install a browser extension to export cookies (e.g., 'Get cookies.txt LOCALLY')\n"
                    "2. Export cookies to a file\n"
                    "3. In VideoLingo settings, set 'youtube.cookies_path' to the cookie file path\n"
                    "See: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"
                ) from e
            if "video unavailable" in err_msg.lower():
                raise RuntimeError(f"Video unavailable: {e}") from e
            raise

        rprint("[yellow]⚠️ YouTube SSL certificate verification failed. Retrying this download with certificate checks disabled...[/yellow]")
        retry_opts = dict(ydl_opts)
        retry_opts["nocheckcertificate"] = True
        with YoutubeDL(retry_opts) as ydl:
            return ydl.extract_info(url, download=True)

def _is_incomplete_download_file(filename):
    return (
        filename.endswith(".part")
        or filename.endswith(".ytdl")
        or ".part-" in filename
        or filename.endswith(".tmp")
    )

def _cleanup_incomplete_downloads(folder):
    if not os.path.isdir(folder):
        return
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and _is_incomplete_download_file(name):
            try:
                os.remove(path)
            except OSError:
                pass

def _unique_output_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base}_v{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1

def _move_download_results(download_dir, save_path):
    moved_files = []
    for name in os.listdir(download_dir):
        src = os.path.join(download_dir, name)
        if not os.path.isfile(src) or _is_incomplete_download_file(name):
            continue
        filename, ext = os.path.splitext(name)
        clean_name = sanitize_filename(filename)
        target = _unique_output_path(os.path.join(save_path, clean_name + ext))
        shutil.move(src, target)
        moved_files.append(target)
    return moved_files

def _extract_video_description(YoutubeDL, url):
    ydl_opts = {
        "noplaylist": True,
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "extract_flat": False,
    }
    cookies_browser = load_key("youtube.cookies_from_browser")
    if cookies_browser and cookies_browser.strip():
        ydl_opts["cookiesfrombrowser"] = (cookies_browser.strip(),)
    else:
        cookies_path = load_key("youtube.cookies_path")
        if os.path.exists(cookies_path):
            ydl_opts["cookiefile"] = str(cookies_path)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return (info or {}).get("description") or ""
    except Exception as e:
        rprint(f"[yellow]Warning: Failed to fetch video description: {e}[/yellow]")
        return ""

def _clean_video_description(description):
    """Remove channel promotion text, keep video-relevant content and timeline/chapters.

    Handles English, Chinese, Japanese, Korean, and other languages.
    """
    if not description:
        return ""
    lines = description.splitlines()
    cleaned = []
    # Word boundary for both Latin (\b) and CJK (zero-width assertion)
    _b = r"(?:\b|(?<![a-zA-Z0-9_]))"
    _o = r"\s*"
    skip_patterns = [
        # === Subscribe / 订阅 ===
        rf"(?i)(subscribed|subscribe|subscri){_b}",
        r"(订阅)",
        # === Follow / 关注 ===
        rf"(?i)(follow|关注){_o}(me|us|my|our|我){_b}",
        # === Social media handles (Twitter: @handle, Instagram: @handle, LinkedIn: /in/handle) ===
        r"(?i)^\s*(twitter|instagram|facebook|linkedin|tiktok|discord|reddit|snapchat|wechat|微博|微信|b站|bilibili|抖音|小红书)\s*[:：]",
        r"(?i)^\s*@\w+\s*$",
        # === Like / share / comment / 点赞 / 投币 / 收藏 / 一键三连 ===
        r"(?i)(like|share|comment)\b.*?(video|this|below|下方|支持)",
        r"(点赞|投币|收藏|一键三连|分享|评论)",
        # === Don't forget / 别忘了 / 记得 + bell/notification patterns ===
        rf"(?i)(don'?t\s+forget|别忘了|记得){_o}(to\s+)?(subscribe|like|share|follow|订阅|关注|点赞|投币|收藏|一键三连|hit the bell|ring the bell|turn on notification|smash the bell|click the bell)",
        # === Bell / notification patterns ===
        r"(?i)(hit the bell|ring the bell|smash the bell|click the bell|turn on notification|notification bell|bell icon|never miss an upload|never miss a video)",
        # === Support / 支持 / 赞助 / 打赏 / donation platforms ===
        rf"(?i)(support|支持){_o}(me|us|my|our|我|the channel|频道|一下){_b}",
        rf"(?i)(patreon|paypal|donate|赞助|打赏|ko-fi|kofi|buymeacoffee|buy me a coffee|cash\s*app|venmo){_b}",
        # === Join channel / Discord / 加入 ===
        rf"(?i)^\s*(join|become|加入){_o}(my|our|this|我的){_o}(channel|membership|member|discord|频道|会员|community)",
        # === Check out my other videos / 查看我的其他视频 / watch next ===
        rf"(?i)(check\s+out|查看|看看|watch next){_o}(my|our|我的){_o}(other\s+videos?|其他|channel|playlist|网站|website|频道|视频|video)",
        # === Thanks / 感谢 (standalone, optionally followed by watching) ===
        rf"(?i)^\s*(thanks?|thank|谢谢|感谢|thank you so much|thx)({_o}(for\s+)?(you|u|大家|watching|观看|收看))?{_b}",
        # === Business inquiries / 商务合作 ===
        rf"(?i)(business\s+inquiries?|商务合作|商务|business){_o}([:：→]|.*?(contact|联系|邮箱|email|请))",
        # === Follow me: @handle / 关注我： ===
        rf"(?i)^\s*(follow|关注){_o}(me|us|我)\s*[:：]",
        # === Social media / SNS / links sections ===
        rf"(?i)^\s*(my|our|我的|我们的)\s+(social|社交媒体|SNS|links?|链接|账号|follow)",
        # === Emoji + subscribe/follow ===
        r"[📱📧📢🔔📌💬👍👆👇👉🎬🔥⭐💼📋]\s*(subscribe|关注|follow|like|share|订阅|support|bell)",
        # === Chinese promo: 求订阅 / 欢迎关注 / 记得点赞 ===
        rf"(?i)^\s*(求|欢迎|记得|帮忙|还请){_o}(订阅|关注|点赞|投币|收藏|分享|一键三连|支持|转发)",
        # === Chinese tail: 支持一下 / 关注一下吧 ===
        rf"(订阅|关注|点赞|投币|收藏|分享|一键三连|支持|转发){_o}(一下|吧|哦|哟)",
        # === Generic: Please subscribe / 请订阅 ===
        rf"(?i)(please|pls|请){_o}(subscribe|订阅|关注|like|share|follow)",
        # === Channel membership / sponsor / 充电 / 会员 ===
        r"(?i)(channel membership|channel member|join this channel|become a member|sponsor|赞助|充电|会员|加入会员)",
                # === "Still haven't subscribed?" / "Haven't subscribed yet?" ===
        r"(?i)(haven'?t\s+)?subscribed\s+(to|on)\s+.{_o}(youtube|our\s+channel)",

        # === "Website:" / "Website - URL" promo ===
        r"(?i)^\s*website\s*[:\-]\s*https?://",

# === Newsletter / mailing list ===
        r"(?i)(newsletter|mailing list|sign up|email list)",
        # === Giveaway / contest ===
        r"(?i)(giveaway|contest|win a|enter to win)",
                # === Discount / promo codes ("Get $X off", "Use code X") ===
        r"(?i)\b(get\s+\$?\d+\s*(%|percent)?\s+off|use\s+(promo\s+)?code\s+\w+|discount\s+code)\b.*https?://",

# === Affiliate links ===
        r"(?i)(affiliate link|aff link|commission earned|paid link)",
        # === Watch/stream full episodes / more episodes (show navigation promo) ===
        r"(?i)^\s*(watch|stream)\s+(full\s+episodes?|more\s+episodes?|all\s+episodes?|the\s+full\s+series)[: ].*https?://",
        # === Get more [content] from [source] (cross-promo navigation) ===
        r"(?i)^\s*get\s+more\s+",
        # === Download our/the app ===
        r"(?i)^\s*download\s+(the|our|my|this|their)\s+.+?\s+app\b",
        # === Try [product/service] free / free trial ===
        r"(?i)\btry\s+(it|them|us|out|.+?)\s+free\b",
        # === For video licensing inquiries / business contact ===
        r"(?i)^\s*for\s+(video\s+)?licensing\s+(inquiries?|requests?)",
        # === Follow [brand] on [social platform]: URL ===
        r"(?i)^\s*follow\s+.+?\s+on\s+(instagram|facebook|twitter|x|tiktok|youtube|linkedin|snapchat|reddit|discord|twitch|threads|whatsapp|telegram|weibo|wechat|bilibili|douyin)[: ].*https?://",
        # === Like [brand] on Facebook: URL ===
        r"(?i)^\s*like\s+.+?\s+on\s+facebook[: ].*https?://",

        # === Separator / decorative rule lines (e.g., "--------------------") ===
        r"^[\s]*[—–_=*#-]{5,}[\s]*$",
        # === Bullet-point cross-promo (▶️ Spotify, ◉ TikTok, ► YouTube, etc.) ===
        r"(?i)^\s*[▶►◉•●○■□◆◇➤➜→⬥⬩].*(https?://|/ ?@|youtube\b|spotify\b|tiktok\b|instagram\b|facebook\b|twitter\b|podcast)",
        # === Watch [show] on [streaming platform] ===
        r"(?i)watch\s+.+?\s+on\s+(bbc\s+iplayer|iplayer|youtube|netflix|hulu|disney\+|prime\s+video|hbo|max|peacock|paramount\+|apple\s+tv\+|amazon\s+prime|itunes|comedy\s+central)",
        # === Stream [content] on [platform] ===
        r"(?i)stream\s+.+?\s+on\s+(paramount\+|netflix|hulu|disney\+|prime\s+video|hbo|peacock|apple\s+tv\+)",
        # === Watch more [channel/content] ===
        r"(?i)^\s*watch\s+more\s+[A-Z]",
        # === Try for free (mid-line variant) ===
        r"(?i)\btry\s+for\s+free\b",
        # === [Name] on [social media] URL (e.g., "Conan O'Brien on Twitter https://...") ===
        r"(?i)^\s*.+?\s+on\s+(twitter|x|instagram|facebook|tiktok|youtube|linkedin|snapchat|reddit|discord|twitch|threads|whatsapp|telegram|weibo|wechat|bilibili|douyin|spotify|apple\s+podcasts)\s+https?://",
        # === Podcast / show name: URL ===

        # === Watch/Stream [show]: URL (e.g., "Watch CBS News: URL", "Watch the BBC first on iPlayer: URL") ===
        r"(?i)(watch|stream)\s+.+?:\s*https?://",
        # === Subscribe NOW to [show]: URL ===
        r"(?i)subscribe\s+now\s+to\s+.+?:?\s*https?://",
        # === Subscribe and [emoji] to [channel]: URL ===
        r"(?i)subscribe\s+and\s+.+?\s+to\s+.+?\s*https?://",
        # === Start learning / Start [action] with [service]: URL (sponsored content) ===
        r"(?i)^\s*start\s+learning\s+.+?\s+(with|on)\s+.+?:\s*https?://",
        # === Learn more about X at [company]: URL ===
        r"(?i)^\s*learn\s+more\s+about\s+.+?(at|on|:)\s*https?://",
        # === "Welcome to the official [company] YouTube channel" boilerplate ===
        r"(?i)^\s*welcome\s+to\s+the\s+official\s+.+?(youtube\s+)?channel",
        # === Corporate boilerplate ("Our more than X employees...", "[Show] is the premier/most successful/leading/largest...") ===
        r"(?i)^\s*our\s+more\s+than\s+\d+.*employees",
        r"(?i)^\s*[\"A-Z0-9][\"A-Za-z0-9\s/]+\s+is\s+the\s+(premier|most\s+successful|leading|largest|anchor)\s",
        # === Read more: URL (standalone, NYT style) ===
        r"(?i)^\s*read\s+more\s*:\s*https?://",
        # === "Want to stay in the know? Subscribe to X" magazine-style promo ===
        r"(?i)^\s*want\s+to\s+stay\s+in\s+the\s+know\?",
# === Bare URL line (standalone URL, almost always promo/secondary) ===
        r"^\s*https?://\S+\s*$",
        # === "More about X" / "Read more" + URL ===
        r"(?i)^\s*(more\s+about|read\s+more|learn\s+more|find\s+out\s+more)\b.*https?://",
        r"(?i)^\s*(the\s+)?[A-Z][a-z]+.+\s+(podcast|show)\s*:\s*https?://",

# === Watch FREE / Watch for free (promo) ===
        r"(?i)^\s*watch\s+free\b",
        r"(?i)^\s*watch\s+.+?\s+for\s+free\b",
        # === Follow / Like [name]: URL (without "on [platform]") ===
        r"(?i)^\s*(follow|like)\s+.+?:\s*https?://(?:www\.)?(twitter\.com|x\.com|instagram\.com|facebook\.com|tiktok\.com|youtube\.com|snapchat\.com|reddit\.com|linkedin\.com|threads\.net|twitch\.tv)",
        # === Merch / Shop / Store links ===
        r"(?i)https?://[^/\s]*\b(shop|store|merch|buy)\b",
        # === Social platform label: URL (e.g., "X: https://twitter.com/...", "Instagram - https://...") ===
        r"(?i)\b(x|twitter|instagram|facebook|tiktok|snapchat|reddit|linkedin|threads|telegram|whatsapp|discord|twitch|tumblr|pinterest)\s*[:\-]\s*https?://",
        # === NBC / Network handle: URL (e.g., "NBC YouTube: http://...", "NBC Instagram: http://...") ===
        r"(?i)^\s*[A-Z]{2,}\s+(youtube|instagram|facebook|twitter|tiktok|snapchat)\s*[:\-]\s*https?://",


        # === Follow / Like [name] on [platform]: URL (e.g., "Follow Jimmy on Threads: URL") ===
        r"(?i)^\s*(follow|like)\s+.+?\s+on\s+(threads|x|twitter|instagram|facebook|tiktok|snapchat|youtube|linkedin|reddit|discord|twitch|tumblr|pinterest)\s*[:\-]\s*https?://",
        # === Section headers: "FOLLOW X:", "X ON SOCIAL", "GET MORE X", "ABOUT X" ===
        r"(?i)^\s*follow\s+[A-Z][A-Za-z\s]+[:：]\s*$",
        r"(?i)^\s*[A-Z\s]+\s+on\s+social\s*$",
        r"(?i)^\s*get\s+more\s+[A-Z][A-Z\s]+\s*$",
        r"(?i)^\s*about\s+[A-Z][A-Za-z\s]+\s*$",
        # === Promotion shorthand at line end ===
        r"(?i)^\s*(sub|like|share|comment|follow)\s*(4|for)\s*(sub|like|share|comment|follow)",
    ]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Always keep timeline / chapter markers
        if re.match(r'^\s*(\d{1,2}[:：]\d{2}([:：]\d{2})?)\s', stripped):
            cleaned.append(stripped)
            continue
        # Keep content hashtags, skip promo ones
        if re.match(r'^#\w+', stripped):
            promo_hashtags = (
                'subscribe', 'follow', 'ad', 'sponsor', 'like4like', 'f4f',
                '订阅', '关注', 'ショート', 'shorts'
            )
            if not any(p in stripped.lower() for p in promo_hashtags):
                cleaned.append(stripped)
            continue
        # Skip channel self-promotion lines
        if any(re.search(p, stripped) for p in skip_patterns):
            continue
        cleaned.append(stripped)
    # Second pass: remove any bare URL lines that survived (safety net)
    result = "\n".join(cleaned).strip()
    lines2 = result.split("\n")
    cleaned = [l for l in lines2 if not re.match(r'^\s*https?://\S+\s*$', l)]
    return "\n".join(cleaned).strip()


def save_video_description(description, save_path="output"):
    os.makedirs(save_path, exist_ok=True)
    cleaned = _clean_video_description(description)
    with open(os.path.join(save_path, "video_description.md"), "w", encoding="utf-8") as f:
        f.write(cleaned)

def download_video_ytdlp(url, save_path='output', resolution='1080'):
    os.makedirs(save_path, exist_ok=True)
    _cleanup_incomplete_downloads(save_path)
    download_dir = tempfile.mkdtemp(prefix=".videolingo_ytdlp_", dir=save_path)
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best' if resolution == 'best' else f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]',
        'outtmpl': os.path.join(download_dir, '%(title).200B.%(ext)s'),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'writethumbnail': True,
        'retries': 10,
        'fragment_retries': 10,
        'file_access_retries': 5,
        'continuedl': False,
        'nopart': True,
        'concurrent_fragment_downloads': 1,
        'socket_timeout': 30,
        # Some local proxy chains expose certificates that Python cannot verify.
        # Keep this scoped to yt-dlp's YouTube download path so the UI can still download.
        'nocheckcertificate': True,
        'postprocessors': [{'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}],
    }

    node_path = shutil.which("node")
    if node_path:
        ydl_opts["js_runtimes"] = {"node": {"path": node_path}}
        ydl_opts["remote_components"] = ["ejs:github"]

    # Read Youtube Cookies — prefer browser cookies, fall back to cookie file
    cookies_browser = load_key("youtube.cookies_from_browser")
    if cookies_browser and cookies_browser.strip():
        ydl_opts["cookiesfrombrowser"] = (cookies_browser.strip(),)
    else:
        cookies_path = load_key("youtube.cookies_path")
        if os.path.exists(cookies_path):
            ydl_opts["cookiefile"] = str(cookies_path)

    # Get YoutubeDL class after updating
    YoutubeDL = update_ytdlp()
    # Download video AND extract description in a single call — avoids separate
    # YouTube request that can fail independently (rate limiting, cookie drift, etc.)
    try:
        info = _download_with_ytdlp(YoutubeDL, ydl_opts, url)
        moved_files = _move_download_results(download_dir, save_path)
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)

    allowed_video_formats = {ext.lower() for ext in load_key("allowed_video_formats")}
    downloaded_videos = [
        path for path in moved_files
        if os.path.splitext(path)[1][1:].lower() in allowed_video_formats
    ]
    if not downloaded_videos:
        raise RuntimeError("Video download finished but no usable video file was produced.")

    description = (info or {}).get("description") or ""
    save_video_description(description, save_path)

def find_video_files(save_path='output'):
    video_files = [file for file in glob.glob(save_path + "/*") if os.path.splitext(file)[1][1:].lower() in load_key("allowed_video_formats")]
    # change \\ to /, this happen on windows
    if sys.platform.startswith('win'):
        video_files = [file.replace("\\", "/") for file in video_files]
    def is_generated_video(file):
        name = os.path.splitext(os.path.basename(file))[0]
        return (
            name.startswith("_")
            or name.startswith("manual_")
            or name.startswith("output")
            or re.search(r"(?:^|_)sub(?:_v\d+)?$", name) is not None
            or re.search(r"(?:^|_)dub(?:_v\d+)?$", name) is not None
        )
    video_files = [
        file for file in video_files
        if not is_generated_video(file)
    ]
    if len(video_files) == 0:
        return None
    if len(video_files) > 1:
        raise ValueError(f"Multiple videos found ({len(video_files)}). Please keep only one video in the output folder.")
    return video_files[0]

if __name__ == '__main__':
    # Example usage
    url = input('Please enter the URL of the video you want to download: ')
    resolution = input('Please enter the desired resolution (360/480/720/1080, default 1080): ')
    resolution = int(resolution) if resolution.isdigit() else 1080
    download_video_ytdlp(url, resolution=resolution)
    print(f"🎥 Video has been downloaded to {find_video_files()}")
