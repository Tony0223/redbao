package com.tonyapp.djxplugin.redpacket;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.tonyfeng.jinshisuda.R;

import java.util.List;

public class RedPacketAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {

    public interface OnRedPacketClickListener {
        void onRedPacketClick(RedPacketItem item, int position);
    }

    private final List<RedPacketItem> items;
    private final OnRedPacketClickListener listener;

    public RedPacketAdapter(List<RedPacketItem> items, OnRedPacketClickListener listener) {
        this.items = items;
        this.listener = listener;
    }

    @Override
    public int getItemViewType(int position) {
        return items.get(position).type;
    }

    @NonNull
    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        LayoutInflater inflater = LayoutInflater.from(parent.getContext());
        if (viewType == RedPacketItem.TYPE_REDPACKET) {
            View v = inflater.inflate(R.layout.item_red_packet_redpacket, parent, false);
            return new RedPacketViewHolder(v);
        } else if (viewType == RedPacketItem.TYPE_AD) {
            View v = inflater.inflate(R.layout.item_red_packet_ad, parent, false);
            return new AdViewHolder(v);
        } else {
            View v = inflater.inflate(R.layout.item_red_packet_text, parent, false);
            return new TextViewHolder(v);
        }
    }

    @Override
    public void onBindViewHolder(@NonNull RecyclerView.ViewHolder holder, int position) {
        RedPacketItem item = items.get(position);
        if (holder instanceof TextViewHolder) {
            TextViewHolder h = (TextViewHolder) holder;
            h.avatar.setText(avatarChar(item.nickname));
            h.nickname.setText(item.nickname);
            h.content.setText(item.content);
        } else if (holder instanceof RedPacketViewHolder) {
            RedPacketViewHolder h = (RedPacketViewHolder) holder;
            h.avatar.setText(avatarChar(item.nickname));
            h.nickname.setText(item.nickname);
            h.hint.setText(item.opened ? "红包已领取" : item.content);
            h.card.setAlpha(item.opened ? 0.5f : 1f);
            h.card.setOnClickListener(v -> {
                if (!item.opened && listener != null) {
                    listener.onRedPacketClick(item, holder.getAdapterPosition());
                }
            });
        } else if (holder instanceof AdViewHolder) {
            AdViewHolder h = (AdViewHolder) holder;
            if (item.adView != null) {
                // 广告View可能之前挂在别的父容器上，先摘掉再重新添加，避免"already has a parent"崩溃
                ViewGroup oldParent = (ViewGroup) item.adView.getParent();
                if (oldParent != null) {
                    oldParent.removeView(item.adView);
                }
                h.container.removeAllViews();
                h.container.addView(item.adView);
            }
        }
    }

    @Override
    public int getItemCount() {
        return items.size();
    }

    /** 昵称首字当头像文字，空的兜个默认 */
    private static String avatarChar(String nickname) {
        if (nickname == null || nickname.isEmpty()) return "群";
        return nickname.substring(0, 1);
    }

    static class TextViewHolder extends RecyclerView.ViewHolder {
        TextView avatar;
        TextView nickname;
        TextView content;
        TextViewHolder(View itemView) {
            super(itemView);
            avatar = itemView.findViewById(R.id.tv_avatar);
            nickname = itemView.findViewById(R.id.tv_nickname);
            content = itemView.findViewById(R.id.tv_content);
        }
    }

    static class RedPacketViewHolder extends RecyclerView.ViewHolder {
        TextView avatar;
        TextView nickname;
        TextView hint;
        View card;
        RedPacketViewHolder(View itemView) {
            super(itemView);
            avatar = itemView.findViewById(R.id.tv_avatar);
            nickname = itemView.findViewById(R.id.tv_nickname);
            hint = itemView.findViewById(R.id.tv_redpacket_hint);
            card = itemView.findViewById(R.id.card_redpacket);
        }
    }

    static class AdViewHolder extends RecyclerView.ViewHolder {
        FrameLayout container;
        AdViewHolder(View itemView) {
            super(itemView);
            container = itemView.findViewById(R.id.container_ad);
        }
    }
}