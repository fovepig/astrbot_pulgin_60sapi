import asyncio
import httpx
import datetime
import random
from typing import Optional, List, Dict

# 导入 AstrBot 核心组件
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 核心：导入消息链和组件
from astrbot.core.message.message_event_result import MessageChain
from astrbot.api.message_components import Image, Plain, Record

def is_cron_time(cron_str: str, now: datetime.datetime):
    """Cron 检查器 (分 时 天 月 周)"""
    try:
        parts = cron_str.split()
        if len(parts) != 5: return False
        current_time = [now.minute, now.hour, now.day, now.month, now.weekday() + 1]
        for i in range(5):
            if parts[i] == '*': continue
            if int(parts[i]) != current_time[i]: return False
        return True
    except: return False

@register("astrbot_pulgin_60sapi", "FovePig", "60s api 综合全功能版", "1.4.5")
class VikiSuperBot(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.base_url = config.get("api_base_url", "https://60s.viki.moe").rstrip("/")
        self.global_groups = config.get("global_target_groups", [])
        
        # 启动定时任务轮询
        asyncio.create_task(self.scheduler_loop())

    async def fetch_api(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """统一请求函数"""
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200: return resp.json()
        except Exception as e:
            logger.error(f"API请求异常 {url}: {e}")
        return None

    def safe_get_text(self, data_obj) -> str:
        """核心修复：安全提取各种接口的文字内容，防止 KeyError"""
        if not data_obj: return "❌ 未获取到数据"
        res = data_obj.get("data")
        if not res: return "❌ 服务器返回数据为空"
        if isinstance(res, str): return res
        if isinstance(res, dict):
            # 兼容所有已知的字段名
            return res.get("text") or res.get("content") or res.get("result") or res.get("cp_content") or res.get("description") or "⚠️ 格式解析失败"
        return str(res)

    async def get_result_chain(self, endpoint: str, params: dict = None, name: str = "数据"):
        """核心修复：统一处理图片结果，防止 KeyError: 'image'"""
        data = await self.fetch_api(endpoint, params)
        if not data or "data" not in data:
            return MessageChain(chain=[Plain(f"❌ 无法从服务器获取{name}")])
        
        res = data["data"]
        if isinstance(res, str): return MessageChain(chain=[Plain(f"💡 {name}: {res}")])
        
        image_url = res.get("image")
        if image_url: return MessageChain(chain=[Image.fromURL(image_url)])
        
        news = res.get("news")
        if news and isinstance(news, list):
            return MessageChain(chain=[Plain(f"【{name}】\n" + "\n".join(news[:15]))])
            
        return MessageChain(chain=[Plain(f"⚠️ {name}暂无图片或内容")])

    async def get_push_targets(self) -> List[str]:
        """留空则推送到所有群组"""
        targets = self.config.get("global_target_groups", [])
        if not targets:
            try:
                all_origins = await self.context.get_all_unified_msg_origins()
                targets = [origin for origin in all_origins if "GroupMessage" in origin]
                if not targets: targets = all_origins 
            except: pass
        return targets

    async def scheduler_loop(self):
        while True:
            now = datetime.datetime.now()
            if self.config.get("enable_60s") and is_cron_time(self.config.get("cron_60s", ""), now):
                await self.simple_push("每日新闻", "/v2/60s")
            if self.config.get("enable_moyu") and is_cron_time(self.config.get("cron_moyu", ""), now):
                await self.simple_push("摸鱼日历", "/v2/moyu")
            if self.config.get("enable_weather") and is_cron_time(self.config.get("cron_weather", ""), now):
                for city in self.config.get("city_weather", ["北京"]):
                    await self.simple_push(f"天气({city})", "/v2/weather", {"city": city})
            if self.config.get("enable_exchange") and is_cron_time(self.config.get("cron_exchange", ""), now):
                await self.simple_push("当日汇率", "/v2/exchange")
            if self.config.get("enable_history") and is_cron_time(self.config.get("cron_history", ""), now):
                await self.simple_push("历史上的今天", "/v2/history")
            await asyncio.sleep(60 - now.second)

    async def simple_push(self, name: str, endpoint: str, params: dict = None):
        chain = await self.get_result_chain(endpoint, params, name)
        targets = await self.get_push_targets()
        for target in targets:
            try: await self.context.send_message(target, chain)
            except: pass

    @filter.command("60help")
    async def help_menu(self, event: AstrMessageEvent):
        help_text = (
            "✨ Viki 助手全功能菜单 ✨\n"
            "━━━━━━━━━━━━━━\n"
            "🛠【实用工具】\n"
            "/60s, /天气 [城市], /汇率, /历史, /百科, /翻译, /whois, /农历, /二维码, /歌词, /黄金, /汽油, /epic\n\n"
            "🔥【实时热榜】\n"
            "/微博, /抖音, /哔哩, /小红书, /头条, /知乎, /懂车帝, /网易云, /热帖, /猫眼\n\n"
            "🎮【娱乐休闲】\n"
            "/点歌, /一言, /运势, /趣题, /段子, /发病, /答案, /kfc, /冷笑话, /摸鱼\n"
            "━━━━━━━━━━━━━━\n"
            "💡 提示: 群号留空则全群推送。"
        )
        yield event.plain_result(help_text)

    # --- 实用工具 ---
    @filter.command("60s")
    async def cmd_60s(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/60s", name="每日新闻"))

    @filter.command("天气")
    async def cmd_weather(self, event: AstrMessageEvent, city: str = "北京"):
        yield event.chain_result(await self.get_result_chain("/v2/weather", {"city": city}, name=f"{city}天气"))

    @filter.command("汇率")
    async def cmd_exchange(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/exchange", name="汇率"))

    @filter.command("历史")
    async def cmd_history(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/history", name="历史上的今天"))

    @filter.command("黄金")
    async def cmd_gold(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/gold", name="黄金价格"))

    @filter.command("汽油")
    async def cmd_petrol(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/petrol", name="汽油价格"))

    @filter.command("epic")
    async def cmd_epic(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/epic", name="Epic游戏"))

    @filter.command("whois")
    async def cmd_whois(self, event: AstrMessageEvent, domain: str):
        data = await self.fetch_api("/v2/whois", {"domain": domain})
        yield event.plain_result(self.safe_get_text(data))

    @filter.command("二维码")
    async def cmd_qrcode(self, event: AstrMessageEvent, text: str):
        yield event.chain_result(await self.get_result_chain("/v2/qrcode", {"text": text}, name="二维码"))

    @filter.command("百科")
    async def cmd_baike(self, event: AstrMessageEvent, word: str):
        data = await self.fetch_api("/v2/baike", {"word": word})
        if data and "data" in data and isinstance(data["data"], dict):
            res = data["data"]
            yield event.plain_result(f"【{res.get('title')}】\n{res.get('description')}\n链接: {res.get('url')}")
        else: yield event.plain_result(f"❌ 未找到词条: {word}")

    @filter.command("歌词")
    async def cmd_lyrics(self, event: AstrMessageEvent, title: str):
        data = await self.fetch_api("/v2/lyrics", {"title": title})
        if data and "data" in data and isinstance(data["data"], dict):
            res = data["data"]
            yield event.plain_result(f"歌名: {res.get('title')}\n歌手: {res.get('artist')}\n\n{res.get('lyrics')}")
        else: yield event.plain_result("❌ 未搜到相关歌词")

    @filter.command("农历")
    async def cmd_lunar(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/lunar")
        if data and "data" in data:
            res = data["data"]
            yield event.plain_result(f"日期: {res.get('date')}\n农历: {res.get('lunarDate')}\n宜: {res.get('suit')}\n忌: {res.get('avoid')}")

    @filter.command("翻译")
    async def cmd_translate(self, event: AstrMessageEvent, text: str, to: str = "zh"):
        data = await self.fetch_api("/v2/translate", {"text": text, "to": to})
        yield event.plain_result(f"翻译结果: {self.safe_get_text(data)}")

    # --- 实时热榜 ---
    @filter.command("微博")
    async def cmd_weibo(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/weibo", name="微博热搜"))

    @filter.command("抖音")
    async def cmd_douyin(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/douyin", name="抖音热搜"))

    @filter.command("哔哩")
    async def cmd_bili(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/bilibili", name="B站热搜"))

    @filter.command("小红书")
    async def cmd_xhs(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/xhs", name="小红书热点"))

    @filter.command("头条")
    async def cmd_toutiao(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/toutiao", name="头条热搜"))

    @filter.command("知乎")
    async def cmd_zhihu(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/zhihu", name="知乎话题"))

    @filter.command("懂车帝")
    async def cmd_dcd(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/dongchedi", name="懂车帝热搜"))

    @filter.command("网易云")
    async def cmd_netease(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/netease_hot", name="网易云热评"))

    @filter.command("热帖")
    async def cmd_hn(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/hn", name="Hacker News"))

    @filter.command("猫眼")
    async def cmd_maoyan(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/maoyan_global", name="猫眼票房"))

    # --- 娱乐休闲 ---
    @filter.command("点歌")
    async def cmd_random_song(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/rand_song")
        if data and "data" in data and isinstance(data["data"], dict):
            res = data["data"]
            url = res.get("url")
            if url:
                yield event.chain_result(MessageChain(chain=[Record.fromURL(url), Plain(f"\n🎵 {res.get('title', '未知')} 下")]))
                return
        yield event.plain_result("❌ 音频获取失败")

    @filter.command("kfc")
    async def cmd_kfc(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/kfc")
        yield event.plain_result(self.safe_get_text(data))

    @filter.command("段子")
    async def cmd_joke(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/joke")
        yield event.plain_result(self.safe_get_text(data))

    @filter.command("发病")
    async def cmd_crazy(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/crazy")
        yield event.plain_result(self.safe_get_text(data))

    @filter.command("一言")
    async def cmd_hitokoto(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/hitokoto")
        yield event.plain_result(self.safe_get_text(data))

    @filter.command("冷笑话")
    async def cmd_cold_joke(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/cold_joke")
        yield event.plain_result(self.safe_get_text(data))

    @filter.command("趣题")
    async def cmd_js_quiz(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/js_quiz")
        if data and "data" in data:
            res = data["data"]
            yield event.plain_result(f"题目：{res.get('question')}\n答案：{res.get('answer')}")

    @filter.command("运势")
    async def cmd_fortune(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/fortune", name="随机运势"))

    @filter.command("答案")
    async def cmd_answer(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/answer", name="答案之书"))

    @filter.command("摸鱼")
    async def cmd_moyu(self, event: AstrMessageEvent):
        yield event.chain_result(await self.get_result_chain("/v2/moyu", name="摸鱼日历"))
