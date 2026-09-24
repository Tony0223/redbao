package com.tonyfeng.jinshisuda.model;

public class WithdrawalRecord {
    public final String amountText;   // 例："¥5.00（500000 金币）"
    public final String statusText;   // 例："审核中"
    public final String status;       // 原始状态码，用于决定颜色
    public final String timeText;     // 例："2026-09-19 14:30:00"

    public WithdrawalRecord(String amountText, String statusText, String status, String timeText) {
        this.amountText = amountText;
        this.statusText = statusText;
        this.status = status;
        this.timeText = timeText;
    }
}