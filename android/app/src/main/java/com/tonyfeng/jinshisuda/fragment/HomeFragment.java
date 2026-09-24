package com.tonyfeng.jinshisuda.fragment;

import android.os.Bundle;
import android.util.DisplayMetrics;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.bytedance.sdk.openadsdk.TTNativeExpressAd;
import com.tonyapp.djxplugin.BannerAdHelper;
import com.tonyfeng.jinshisuda.R;
import com.tonyfeng.jinshisuda.api.ApiClient;

import org.json.JSONObject;

public class HomeFragment extends Fragment {

    private TTNativeExpressAd bannerAd;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View root = inflater.inflate(R.layout.fragment_home, container, false);
        View.OnClickListener openListener = v -> Toast.makeText(requireContext(), "即将上线，敬请期待", Toast.LENGTH_SHORT).show();
        root.findViewById(R.id.btn_open_recommend).setOnClickListener(openListener);
        root.findViewById(R.id.btn_open_list_item).setOnClickListener(openListener);

        loadBannerText(root);
        loadBanner(root);
        return root;
    }

    /**
     * 拉取后台配置的横幅文案，设置到橙色横幅上（后台 /admin/settings 可改）。
     * 拉不到就用布局里的默认文案兜底。
     */
    private void loadBannerText(View root) {
        TextView title = root.findViewById(R.id.home_banner_title);
        TextView subtitle = root.findViewById(R.id.home_banner_subtitle);
        ApiClient.getAppConfig(new ApiClient.ApiCallback() {
            @Override
            public void onSuccess(JSONObject data) {
                if (!isAdded()) return;
                String t = data.optString("home_banner_title", "");
                String s = data.optString("home_banner_subtitle", "");
                requireActivity().runOnUiThread(() -> {
                    if (!isAdded()) return;
                    if (title != null && !t.isEmpty()) title.setText(t);
                    if (subtitle != null && !s.isEmpty()) subtitle.setText(s);
                });
            }

            @Override
            public void onError(String message) {
                // 拉不到就用默认文案，不处理
            }
        });
    }

    /**
     * 加载首页 Banner 广告，成功就盖在橙色横幅上，失败就留橙色横幅兜底。
     */
    private void loadBanner(View root) {
        FrameLayout adContainer = root.findViewById(R.id.home_banner_ad_container);
        View fallback = root.findViewById(R.id.home_banner_fallback);

        DisplayMetrics dm = getResources().getDisplayMetrics();
        float density = dm.density <= 0 ? 1f : dm.density;
        // 横幅在外层 padding 16dp 里，实际可用宽度 = 屏宽 - 左右各16dp
        float widthDp = dm.widthPixels / density - 32f;

        BannerAdHelper.load(requireActivity(), widthDp, 0f, new BannerAdHelper.BannerCallback() {
            @Override
            public void onAdReady(TTNativeExpressAd ad, View adView) {
                if (!isAdded() || adContainer == null) {
                    try { ad.destroy(); } catch (Throwable ignore) {}
                    return;
                }
                // 先销毁上一条，再挂新的
                if (bannerAd != null) {
                    try { bannerAd.destroy(); } catch (Throwable ignore) {}
                }
                bannerAd = ad;

                if (adView.getParent() instanceof ViewGroup) {
                    ((ViewGroup) adView.getParent()).removeView(adView);
                }
                adContainer.removeAllViews();
                FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.gravity = android.view.Gravity.CENTER;
                adContainer.addView(adView, lp);
                adContainer.setVisibility(View.VISIBLE);   // 广告盖上去
            }

            @Override
            public void onAdFail(String reason) {
                // 拿不到广告：什么都不做，橙色横幅继续兜底
                if (adContainer != null) adContainer.setVisibility(View.GONE);
                if (fallback != null) fallback.setVisibility(View.VISIBLE);
            }
        });
    }

    @Override
    public void onDestroyView() {
        if (bannerAd != null) {
            try { bannerAd.destroy(); } catch (Throwable ignore) {}
            bannerAd = null;
        }
        super.onDestroyView();
    }
}
