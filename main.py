from __future__ import annotations

import ctypes
import sys

from warframe_agent import config
from warframe_agent.agent import WarframeAgent
from warframe_agent.chat import ChatAgent, call_ollama_router, is_chat_exit
from warframe_agent.monitor import PriceMonitor
from warframe_agent.price_history import PriceHistoryDB


def configure_console_encoding() -> None:
    if sys.platform != "win32":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except OSError:
                pass
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def print_menu() -> None:
    print("\n=== Warframe \u672c\u5730\u4ea4\u6613 Agent ===")
    print(f"\u5f53\u524d\u5bf9\u8bdd\u6a21\u578b\uff1a{config.MODEL_NAME}")
    print("1. \u67e5\u8be2\u5355\u4e2a\u7269\u54c1")
    print("2. \u751f\u6210\u6bcf\u65e5\u4ef7\u683c\u8868")
    print("3. \u91cd\u5efa\u672c\u5730\u7269\u54c1\u5b57\u5178")
    print("4. \u5bf9\u8bdd\u5f0f\u4ea4\u6613\u52a9\u624b")
    print("q. \u9000\u51fa")


def handle_lookup(agent: WarframeAgent) -> None:
    name = input("\n\u8bf7\u8f93\u5165\u7269\u54c1\u4e2d\u6587\u540d/\u82f1\u6587\u540d/market id\uff1a").strip()
    if not name:
        print("\u7269\u54c1\u540d\u4e0d\u80fd\u4e3a\u7a7a\u3002")
        return
    try:
        result = agent.lookup_item(name)
        print(result.text)
    except Exception as exc:
        print(f"\u67e5\u8be2\u5931\u8d25\uff1a{exc}")
        print("\u5efa\u8bae\uff1a\u68c0\u67e5\u7f51\u7edc/Ollama\uff0c\u6216\u628a\u522b\u540d\u52a0\u5165 data/item_aliases.json\u3002")


def handle_report(agent: WarframeAgent) -> None:
    try:
        report_path = agent.generate_daily_report()
        print(agent.daily_summary(report_path))
    except Exception as exc:
        print(f"\u751f\u6210\u65e5\u62a5\u5931\u8d25\uff1a{exc}")


def handle_rebuild(agent: WarframeAgent) -> None:
    try:
        count = agent.rebuild_dictionary()
        print(f"\u672c\u5730\u7269\u54c1\u5b57\u5178\u5df2\u91cd\u5efa\uff0c\u5171 {count} \u6761\u6620\u5c04\u3002")
    except Exception as exc:
        print(f"\u91cd\u5efa\u5b57\u5178\u5931\u8d25\uff1a{exc}")


def handle_chat(agent: WarframeAgent) -> None:
    price_db = PriceHistoryDB()
    chat_agent = ChatAgent(resolver=agent.resolver, price_db=price_db, router_call=call_ollama_router)
    monitor = PriceMonitor()
    monitor.start()
    print("\n\u8fdb\u5165\u5bf9\u8bdd\u5f0f\u4ea4\u6613\u52a9\u624b\u3002\u8f93\u5165 q / quit / \u9000\u51fa \u8fd4\u56de\u4e3b\u83dc\u5355\u3002")
    print("\u793a\u4f8b\uff1a\u5145\u6c9b\u73b0\u5728\u80fd\u4e70\u5417\uff1f / \u5ddd\u6d41p\u591a\u5c11\u94b1\u51fa\u5408\u9002\uff1f")
    print("\u8bb0\u5fc6\u547d\u4ee4\uff1a/memory \u67e5\u770b\u8bb0\u5fc6\uff0c/fav add \u5145\u6c9b\uff0c/alert add \u5145\u6c9b below 45\uff0c/scan \u626b\u63cf\u5173\u6ce8\uff0c/pref platform pc")
    try:
        while True:
            for notification in monitor.drain_notifications():
                print(f"\n[\u63d0\u9192] {notification.item_display}: \u5f53\u524d {notification.current_price}p\uff0c{notification.alert.note}")
            message = input("\n\u4f60\uff1a").strip()
            if is_chat_exit(message):
                print("\u5df2\u9000\u51fa\u5bf9\u8bdd\u6a21\u5f0f\u3002")
                return
            if not message:
                continue
            print(f"\nAgent\uff1a{chat_agent.answer(message)}")
    finally:
        monitor.stop()


def main() -> None:
    configure_console_encoding()
    agent = WarframeAgent()
    while True:
        print_menu()
        choice = input("\u8bf7\u9009\u62e9\uff1a").strip().lower()
        if choice == "1":
            handle_lookup(agent)
        elif choice == "2":
            handle_report(agent)
        elif choice == "3":
            handle_rebuild(agent)
        elif choice == "4":
            handle_chat(agent)
        elif choice == "q":
            print("\u5df2\u9000\u51fa\u3002")
            break
        else:
            print("\u65e0\u6548\u9009\u9879\uff0c\u8bf7\u8f93\u5165 1\u30012\u30013\u30014 \u6216 q\u3002")


if __name__ == "__main__":
    main()
