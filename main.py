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

@register("viki_super_bot", "Developer", "功能极度丰富的 60s-api 综合插件", "1.2.0")
class VikiSuperBot(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.base_url = config.get("api_base_url", "https://60s.viki.moe").rstrip("/")
        self.services = config.get("services", {})
        self.global_groups = config.get("global_target_groups", [])
        
        # 启动定时任务
        asyncio.create_task(self.scheduler_loop())

    async def fetch_api(self, endpoint: str, params: dict = None) -> Optional[dict]:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200: return resp.json()
        except Exception as e:
            logger.error(f"API请求异常 {url}: {e}")
        return None

    async def scheduler_loop(self):
        while True:
            now = datetime.datetime.now()
            for name, cfg in self.services.items():
                if cfg.get("enabled") and is_cron_time(cfg.get("cron", ""), now):
                    await self.execute_push(name, cfg)
            await asyncio.sleep(60 - now.second)

    async def execute_push(self, name: str, cfg: dict):
        data = await self.fetch_api(cfg.get("endpoint"), {"city": cfg.get("city", "北京")})
        if not data or "data" not in data: return
        chain = MessageChain()
        res = data["data"]
        if isinstance(res, dict) and "image" in res:
            chain.add(Image.fromURL(res["image"]))
        elif "news" in res:
            chain.add(Plain(f"【{name}】\n" + "\n".join(res["news"][:15])))
        
        targets = cfg.get("targets") or self.global_groups
        for target in targets:
            await self.context.send_message(target, chain)

    # --- 帮助菜单 ---
    @filter.command("60help")
    async def help_menu(self, event: AstrMessageEvent):
        help_text = "✨ Viki 助手功能列表 ✨\n"
        help_text += "━━━━━━━━━━━━━━\n"
        help_text += "🛠【实用工具】\n"
        help_text += "/60s, /天气 [城市], /汇率, /历史, /摸鱼, /百科 [词条], /翻译 [文] [语言], /whois [域名], /农历, /二维码 [文], /歌词 [名], /黄金, /汽油, /epic\n\n"
        help_text += "🔥【实时热榜】\n"
        help_text += "/微博, /抖音, /哔哩, /小红书, /头条, /知乎, /懂车帝, /猫眼, /热帖(HN), /网易云\n\n"
        help_text += "🎮【娱乐休闲】\n"
        help_text += "/点歌, /一言, /运势, /趣题, /段子, /发病, /答案, /kfc, /冷笑话\n"
        help_text += "━━━━━━━━━━━━━━\n"
        help_text += "💡 提示：定时推送请在后台 config 配置。"
        yield event.plain_result(help_text)

    # --- 1. 实用工具指令 (部分示例，结构一致) ---
    @filter.command("60s")
    async def cmd_60s(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/60s")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("天气")
    async def cmd_weather(self, event: AstrMessageEvent, city: str = "北京"):
        data = await self.fetch_api("/v2/weather", {"city": city})
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    # --- 2. 实时热榜指令 (V2 接口大部分返回图片) ---
    @filter.command("微博")
    async def cmd_weibo(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/weibo")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("抖音")
    async def cmd_douyin(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/douyin")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("哔哩")
    async def cmd_bili(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/bilibili")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("小红书")
    async def cmd_xhs(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/xhs")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("知乎")
    async def cmd_zhihu(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/zhihu")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("懂车帝")
    async def cmd_dcd(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/dongchedi")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("热帖")
    async def cmd_hn(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/hn")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("猫眼")
    async def cmd_maoyan(self, event: AstrMessageEvent):
        # 默认取全球票房，你也可以加参数
        data = await self.fetch_api("/v2/maoyan_global")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    # --- 3. 娱乐功能指令 ---
    @filter.command("点歌")
    async def cmd_random_song(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/rand_song") # 假设 endpoint 是这个
        if data and "data" in data:
            res = data["data"]
            # AstrBot 发送音频组件
            yield event.chain_result(MessageChain().add(Record.fromURL(res["url"])).add(Plain(f"\n🎵 {res.get('title')}")))

    @filter.command("一言")
    async def cmd_hitokoto(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/hitokoto")
        if data: yield event.plain_result(f"「{data['data']['text']}」 —— {data['data']['author']}")

    @filter.command("运势")
    async def cmd_fortune(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/fortune")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("发病")
    async def cmd_crazy(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/crazy")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("段子")
    async def cmd_joke(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/joke")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("kfc")
    async def cmd_kfc(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/kfc")
        if data: yield event.plain_result(data["data"]["text"])

    @filter.command("答案")
    async def cmd_answer(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/answer")
        if data: yield event.chain_result(MessageChain().add(Image.fromURL(data["data"]["image"])))

    @filter.command("冷笑话")
    async def cmd_cold_joke(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/cold_joke")
        if data: yield event.plain_result(data["data"]["text"])
        
    @filter.command("趣题")
    async def cmd_js_quiz(self, event: AstrMessageEvent):
        data = await self.fetch_api("/v2/js_quiz")
        if data: yield event.plain_result(f"题目：{data['data']['question']}\n\n答案：{data['data']['answer']}")

    # --- 补充的其他指令 (如黄金、汽油、Epic 等请参照上文格式添加) ---
