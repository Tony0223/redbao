"""统一金币流水。

原来每种玩法各有各的表（AdWatchLog / RebateLog / SignInLog / PunchLog / WheelDrawRecord…），
要出一个"收入明细"就得查六张表再合并排序，分页很难写，以后加玩法还得改。
这里加一张总账表，发币的地方顺手写一条，明细页只查这一张。

各玩法自己的表不动，它们还承担各自的业务逻辑（比如签到防重复、打卡排名），
coin_logs 只负责"谁、什么时候、因为什么、加/减了多少金币"。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from app.database import Base


class CoinSource:
    """流水来源。写死成常量，别用枚举，以后加玩法不用改表结构。"""

    AD = "ad"                # 看广告
    REBATE = "rebate"        # 徒弟返利
    SIGNIN = "signin"        # 每日签到
    PUNCH = "punch"          # 每日打卡
    BONUS = "bonus"          # 福利活动
    WHEEL = "wheel"          # 幸运转盘
    SUBSIDY = "subsidy"      # 提现补贴
    WITHDRAW = "withdraw"    # 提现扣除（负数）
    REFUND = "refund"        # 提现驳回退回
    ADMIN = "admin"          # 后台手动调整


SOURCE_LABELS = {
    CoinSource.AD: "看广告奖励",
    CoinSource.REBATE: "徒弟返利",
    CoinSource.SIGNIN: "每日签到",
    CoinSource.PUNCH: "每日打卡",
    CoinSource.BONUS: "福利活动",
    CoinSource.WHEEL: "幸运转盘",
    CoinSource.SUBSIDY: "提现补贴",
    CoinSource.WITHDRAW: "提现扣除",
    CoinSource.REFUND: "提现退回",
    CoinSource.ADMIN: "系统调整",
}


class CoinLog(Base):
    __tablename__ = "coin_logs"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    source = Column(String(16), index=True, nullable=False, comment="来源，见 CoinSource")
    coins = Column(Integer, nullable=False, comment="金币变动，正数入账负数出账")
    balance_after = Column(Integer, nullable=True, comment="变动后余额，对账用，拿不到就留空")
    remark = Column(String(100), nullable=True, comment="补充说明，如 第3天签到")
    created_at = Column(DateTime, default=datetime.now, index=True, comment="发生时间")


def log_coin(
    db: Session,
    user_id: int,
    source: str,
    coins: int,
    remark: str = "",
    balance_after: int = None,
    commit: bool = False,
) -> None:
    """记一条流水。

    默认不 commit，跟在调用方自己的事务里一起提交，免得把人家的事务打断。
    调用方如果已经 commit 过了，传 commit=True 单独提交这一条。
    coins 为 0 直接跳过，不留没意义的记录。
    """
    if not coins:
        return
    db.add(
        CoinLog(
            user_id=user_id,
            source=source,
            coins=coins,
            balance_after=balance_after,
            remark=(remark or "")[:100],
            created_at=datetime.now(),
        )
    )
    if commit:
        db.commit()
