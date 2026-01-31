import asyncio
import httpx
import datetime
import random
from typing import Optional, List, Dict
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.message_event_result import MessageChain
from astrbot.api.message_components import Image, Plain, Record

def is_cron_time(cron_str: str, now: datetime.datetime):
    try:
        parts = cron_str.split()
        if len(parts) != 5: return False
        current_time = [now.minute, now.hour, now.day, now.month, now.weekday() + 1]
        for i in range(5):
            if parts[i] == '*': continue
            if int(parts[i]) != current_time[i]: return False
        return True
    except: return False

@register("astrbot_pulgin_60sapi", "FovePig", "60s api 集合", "0.1.1")
class VikiSuperBot(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.base_url = config.get("api_base_url", "https://60s.viki.moe").rstrip("/")
        
        # 启动定时任务轮询
        asyncio.create_task(self.scheduler_loop())

    async def fetch_api(self, endpoint: str, params: dict = None) -> Optional[dict]:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200: return resp.json()
        except Exception as e:
            logger.error(f"API异常 {url}: {e}")
        return None

    async def get_push_targets(self) -> List[str]:
        """智能获取推送目标：配置为空则获取所有群组"""
        targets = self.config.get("global_target_groups", [])
        if not targets:
            try:
                # 获取机器人所在的所有统一消息源
                all_origins = await self.context.get_all_unified_msg_origins()
                # 优先推送给群组
                targets = [origin for origin in all_origins if "GroupMessage" in origin]
                if not targets: targets = all_origins 
            except Exception as e:
                logger.error(f"自动获取群组列表失败: {e}")
        return targets

    async def scheduler_loop(self):
        while True:
            now = datetime.datetime.now()
            # 1. 60s新闻
            if self.config.get("enable_60s") and is_cron_time(self.config.get("cron_60s", ""), now):
                await self.simple_push("每日新闻", "/v2/60s")
            
            # 2. 摸鱼日历
            if self.config.get("enable_moyu") and is_cron_time(self.config.get("cron_moyu", ""), now):
                await self.simple_push("摸鱼日历", "/v2/moyu")
            
            # 3. 天气推送（支持多城市）
            if self.config.get("enable_weather") and is_cron_time(self.config.get("cron_weather", ""), now):
                cities = self.config.get("city_weather", ["北京"])
                for city in cities:
                    await self.simple_push(f"天气预报({city})", "/v2/weather", {"city": city})
            
            # 4. 汇率推送
            if self.config.get("enable_exchange") and is_cron_time(self.config.get("cron_exchange", ""), now):
                await self.simple_push("当日汇率", "/v2/exchange")
            
            # 5. 历史上的今天
            if self.config.get("enable_history") and is_cron_time(self.config.get("cron_history", ""), now):
                await self.simple_push("历史上的今天", "/v2/history")

            await asyncio.sleep(60 - now.second)

    async def simple_push(self, name: str, endpoint: str, params: dict = None):
        data = await self.fetch_api(endpoint, params)
        if not data or "data" not in data: return
        res = data["data"]
        
        # 构造消息组件列表
        components = []
        if isinstance(res, dict) and "image" in res:
            components.append(Image.fromURL(res["image"]))
        elif isinstance(res, dict) and "news" in res:
            text = f"【{name}】\n" + "\n".join(res["news"][:15])
            components.append(Plain(text))
        
        if not components: return
        
        # 构造 MessageChain
        chain = MessageChain(chain=components)
        
        targets = await self.get_push_targets()
        for target in targets:
            try: 
                await self.context.send_message(target, chain)
            except Exception as e: 
                logger.error(f"推送至 {target} 失败: {e}")

    # ==========================
    #      指令部分
    # ==========================
    @filter.command("60help")
    async def help_menu(self, event: AstrMessageEvent):
        help_text = (
            "✨ 60s 助手全功能菜单 ✨\n"
            "━━━━━━━━━━━━━━\n"
            "🛠【实用工具】\n"
            "/60s, /天气 [城市], /汇率, /历史, /百科 [词条], /翻译 [文] [语言], /whois [域名], /农历, /二维码 [文], /歌词 [名], /黄金, /汽油, /epic\n\n"
            "🔥【实时热榜】\n"
            "/微博, /抖音, /哔哩, /小红书, /头条, /知乎, /懂车帝, /网易云, /热帖, /猫眼\n\n"
            "🎮【娱乐休闲】\n"
            "/点歌, /一言, /运势, /趣题, /段子, /发病, /答案, /kfc, /冷笑话, /摸鱼\n"
            "━━━━━━━━━━━━━━\n"
            "💡 提示: 推送群号留空则默认全发。"
        )
        yield event.plain_result(help_text)

    @filter.command("60s")
    async def cmd_60s(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/60s")
        if data and "data" in data:
            yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("天气")
    async def cmd_weather(self, event: AstrMessageEvent, city: str = "北京"):
        data = await self.fetch_api("/v2/weather", {"city": city})
        if data and "data" in data:
            yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("汇率")
    async def cmd_exchange(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/exchange")
        if data and "data" in data:
            yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("历史")
    async def cmd_history(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/history")
        if data and "data" in data:
            yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("微博")
    async def cmd_weibo(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/weibo")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("抖音")
    async def cmd_douyin(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/douyin")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("哔哩")
    async def cmd_bili(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/bilibili")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("小红书")
    async def cmd_xhs(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/xhs")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("头条")
    async def cmd_toutiao(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/toutiao")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("知乎")
    async def cmd_zhihu(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/zhihu")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("懂车帝")
    async def cmd_dcd(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/dongchedi")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("网易云")
    async def cmd_netease(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/netease_hot")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("热帖")
    async def cmd_hn(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/hn")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("猫眼")
    async def cmd_maoyan(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/maoyan_global")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("点歌")
    async def cmd_random_song(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/rand_song")
        if data and "data" in data:
            res = data["data"]
            yield event.chain_result(MessageChain(chain=[Record.fromURL(res["url"]), Plain(f"\n🎵 {res.get('title')}下")]))

    @filter.command("一言")
    async def cmd_hitokoto(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/hitokoto")
        if data: yield event.plain_result(f"「{data['data']['text']}」 —— {data['data']['author']}")

    @filter.command("运势")
    async def cmd_fortune(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/fortune")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("百科")
    async def cmd_baike(self, event: AstrMessageEvent, word: str):
        data = await self.fetch_api("/v2/baike", {"word": word})
        if data and "data" in data:
            res = data["data"]
            yield event.plain_result(f"【{res.get('title')}】\n{res.get('description')}\n链接: {res.get('url')}")

    @filter.command("翻译")
    async def cmd_translate(self, event: AstrMessageEvent, text: str, to: str = "zh"):
        data = await self.fetch_api("/v2/translate", {"text": text, "to": to})
        if data: yield event.plain_result(f"翻译结果: {data['data']['result']}")

    @filter.command("whois")
    async def cmd_whois(self, event: AstrMessageEvent, domain: str):
        data = await self.fetch_api("/v2/whois", {"domain": domain})
        if data: yield event.plain_result(f"Whois 信息:\n{data['data']['result']}")

    @filter.command("农历")
    async def cmd_lunar(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/lunar")
        if data:
            res = data["data"]
            yield event.plain_result(f"日期: {res.get('date')}\n农历: {res.get('lunarDate')}\n宜: {res.get('suit')}\n忌: {res.get('avoid')}")

    @filter.command("二维码")
    async def cmd_qrcode(self, event: AstrMessageEvent, text: str):
        data = await self.fetch_api("/v2/qrcode", {"text": text})
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("歌词")
    async def cmd_lyrics(self, event: AstrMessageEvent, title: str):
        data = await self.fetch_api("/v2/lyrics", {"title": title})
        if data and "data" in data:
            res = data["data"]
            yield event.plain_result(f"歌名: {res.get('title')}\n歌手: {res.get('artist')}\n\n{res.get('lyrics')}")

    @filter.command("黄金")
    async def cmd_gold(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/gold")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("汽油")
    async def cmd_petrol(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/petrol")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("epic")
    async def cmd_epic(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/epic")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("趣题")
    async def cmd_js_quiz(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/js_quiz")
        if data: yield event.plain_result(f"题目：{data['data']['question']}\n答案：{data['data']['answer']}")

    @filter.command("段子")
    async def cmd_joke(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/joke")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("发病")
    async def cmd_crazy(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/crazy")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("答案")
    async def cmd_answer(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/answer")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))

    @filter.command("kfc")
    async def cmd_kfc(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/kfc")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("冷笑话")
    async def cmd_cold_joke(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/cold_joke")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("摸鱼")
    async def cmd_moyu(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/moyu")
        if data: yield event.chain_result(MessageChain(chain=[Image.fromURL(data["data"]["image"])]))
