"""GXCode UIController — 界面控制抽象

命令通过此接口操作 UI，不直接绑定 Textual widget。
"""

from abc import ABC, abstractmethod


class UIController(ABC):
    """界面控制接口 — 命令实现的唯一 UI 入口"""

    @abstractmethod
    def add_message(self, text: str) -> None:
        """在聊天区域显示一条消息"""
        ...

    @abstractmethod
    def send_user_message(self, text: str) -> None:
        """以用户身份发送消息给 Agent（触发 Agent 循环）"""
        ...

    @abstractmethod
    def set_mode(self, mode: str) -> None:
        """切换模式：'plan' | 'act'"""
        ...

    @abstractmethod
    def get_mode(self) -> str:
        """获取当前模式"""
        ...

    @abstractmethod
    def set_permission_mode(self, mode: str) -> None:
        """切换权限模式：'strict' | 'default' | 'permissive' | 'custom'"""
        ...

    @abstractmethod
    def get_permission_mode(self) -> str:
        """获取当前权限模式"""
        ...

    @abstractmethod
    def get_token_usage(self) -> tuple[int, int]:
        """获取累计 token 用量 (prompt, completion)"""
        ...

    @abstractmethod
    def refresh_status(self) -> None:
        """刷新状态栏"""
        ...

    @abstractmethod
    def clear_chat(self) -> None:
        """清空聊天区域"""
        ...

    @abstractmethod
    def trigger_context_compression(self) -> None:
        """触发上下文压缩"""
        ...

    @abstractmethod
    def get_session_info(self) -> dict:
        """获取当前会话信息"""
        ...