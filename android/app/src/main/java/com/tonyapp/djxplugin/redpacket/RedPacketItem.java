package com.tonyapp.djxplugin.redpacket;

import android.view.View;

public class RedPacketItem {

    public static final int TYPE_TEXT = 0;
    public static final int TYPE_REDPACKET = 1;
    public static final int TYPE_AD = 2;

    public int type;
    public String nickname;
    public String content;
    public boolean opened;
    public View adView; // 模板渲染模式下，SDK已经渲染好的完整广告View

    public static RedPacketItem newText(String nickname, String content) {
        RedPacketItem item = new RedPacketItem();
        item.type = TYPE_TEXT;
        item.nickname = nickname;
        item.content = content;
        return item;
    }

    public static RedPacketItem newRedPacket(String nickname) {
        RedPacketItem item = new RedPacketItem();
        item.type = TYPE_REDPACKET;
        item.nickname = nickname;
        item.content = "送上红包，愿您财源滚滚";
        item.opened = false;
        return item;
    }

    public static RedPacketItem newAd(View adView) {
        RedPacketItem item = new RedPacketItem();
        item.type = TYPE_AD;
        item.adView = adView;
        return item;
    }
}