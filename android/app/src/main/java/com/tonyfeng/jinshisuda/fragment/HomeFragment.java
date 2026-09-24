package com.tonyfeng.jinshisuda.fragment;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.tonyfeng.jinshisuda.R;

public class HomeFragment extends Fragment {
    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View root = inflater.inflate(R.layout.fragment_home, container, false);
        View.OnClickListener openListener = v -> Toast.makeText(requireContext(), "即将上线，敬请期待", Toast.LENGTH_SHORT).show();
        root.findViewById(R.id.btn_open_recommend).setOnClickListener(openListener);
        root.findViewById(R.id.btn_open_list_item).setOnClickListener(openListener);
        return root;
    }
}