package com.tonyfeng.jinshisuda.adapter;

import android.graphics.Color;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.model.WithdrawalRecord;

import java.util.ArrayList;
import java.util.List;

public class WithdrawalRecordAdapter
        extends RecyclerView.Adapter<WithdrawalRecordAdapter.VH> {

    private final List<WithdrawalRecord> data = new ArrayList<>();

    public void setData(List<WithdrawalRecord> list) {
        data.clear();
        if (list != null) data.addAll(list);
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_withdrawal_record, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH h, int position) {
        WithdrawalRecord r = data.get(position);
        h.tvAmount.setText(r.amountText);
        h.tvStatus.setText(r.statusText);
        h.tvStatus.setTextColor(colorForStatus(r.status));
        h.tvTime.setText(r.timeText);
    }

    @Override
    public int getItemCount() {
        return data.size();
    }

    private int colorForStatus(String status) {
        if (status == null) return Color.parseColor("#666666");
        switch (status) {
            case "success":     return Color.parseColor("#2E7D32"); // 绿：已到账
            case "failed":      return Color.parseColor("#C62828"); // 红：打款失败
            case "pending":     return Color.parseColor("#EF6C00"); // 橙：审核中
            case "processing":  return Color.parseColor("#1565C0"); // 蓝：打款中
            default:            return Color.parseColor("#666666");
        }
    }

    static class VH extends RecyclerView.ViewHolder {
        TextView tvAmount, tvStatus, tvTime;
        VH(@NonNull View v) {
            super(v);
            tvAmount = v.findViewById(R.id.tv_amount);
            tvStatus = v.findViewById(R.id.tv_status);
            tvTime = v.findViewById(R.id.tv_time);
        }
    }
}