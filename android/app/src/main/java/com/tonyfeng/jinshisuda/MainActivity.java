package com.tonyfeng.jinshisuda;

import android.os.Bundle;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.tonyfeng.jinshisuda.api.InviteCodeStore;
import com.tonyfeng.jinshisuda.fragment.HomeFragment;
import com.tonyfeng.jinshisuda.fragment.InviteFragment;
import com.tonyfeng.jinshisuda.fragment.MineFragment;
import com.tonyfeng.jinshisuda.fragment.RedPacketFragment;
import com.tonyfeng.jinshisuda.fragment.WelfareFragment;
import com.tonyfeng.jinshisuda.view.FeedAdDrawer;
import com.tonyfeng.jinshisuda.view.InterstitialAdManager;

public class MainActivity extends AppCompatActivity {

    private final Fragment homeFragment = new HomeFragment();
    private final Fragment redPacketFragment = new RedPacketFragment();
    private final Fragment inviteFragment = new InviteFragment();
    private final Fragment welfareFragment = new WelfareFragment();
    private final Fragment mineFragment = new MineFragment();

    private Fragment currentFragment;
    /** 提成字段，好让 Fragment 能切 tab（比如"我的"页点"我的好友"跳到邀请页） */
    private BottomNavigationView bottomNav;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 首次进入默认显示首页
        getSupportFragmentManager().beginTransaction()
                .add(R.id.fragment_container, homeFragment, "home")
                .add(R.id.fragment_container, redPacketFragment, "redpacket")
                .add(R.id.fragment_container, inviteFragment, "invite")
                .add(R.id.fragment_container, welfareFragment, "welfare")
                .add(R.id.fragment_container, mineFragment, "mine")
                .commit();

        currentFragment = homeFragment;
        // 先隐藏除首页外的所有fragment（等commit生效后再统一hide，避免闪烁，简单起见分两步）
        getSupportFragmentManager().executePendingTransactions();
        getSupportFragmentManager().beginTransaction()
                .hide(redPacketFragment)
                .hide(inviteFragment)
                .hide(welfareFragment)
                .hide(mineFragment)
                .commit();

        bottomNav = findViewById(R.id.bottom_nav);
        bottomNav.setOnItemSelectedListener(this::onNavItemSelected);

        // 默认停在首页，抽屉正常显示（从红包群 tab 杀进程重开时也会回到这里）
        FeedAdDrawer.resumeFrom(this);
        InterstitialAdManager.resumeFrom(this);
    }

    /**
     * 切到邀请 tab。"我的"页的"我的好友"和邀请横幅都走这里。
     * 走 setSelectedItemId 而不是直接切 fragment，这样底部导航的选中态也会跟着变。
     */
    public void switchToInvite() {
        if (bottomNav != null) {
            bottomNav.setSelectedItemId(R.id.nav_invite);
        }
    }

    /** 切到福利 tab，以后别的页面要跳也用得上 */
    public void switchToWelfare() {
        if (bottomNav != null) {
            bottomNav.setSelectedItemId(R.id.nav_welfare);
        }
    }

    private boolean onNavItemSelected(@NonNull android.view.MenuItem item) {
        Fragment target;
        int id = item.getItemId();
        if (id == R.id.nav_home) {
            target = homeFragment;
        } else if (id == R.id.nav_redpacket) {
            target = redPacketFragment;
        } else if (id == R.id.nav_invite) {
            target = inviteFragment;
        } else if (id == R.id.nav_welfare) {
            target = welfareFragment;
        } else if (id == R.id.nav_mine) {
            target = mineFragment;
        } else {
            return false;
        }

        if (target == currentFragment) {
            return true;
        }

        // 红包群那个 tab 的聊天气泡里本来就有信息流，底部再来一条抽屉
        // 容易被穿山甲判成广告堆叠扣量，所以切到红包群就把抽屉收起来；
        // 插屏也一样，红包群页不弹插屏，切到其他 tab 再恢复
        if (target == redPacketFragment) {
            FeedAdDrawer.suspend(this);
            InterstitialAdManager.suspend(this);
        } else {
            FeedAdDrawer.resumeFrom(this);
            InterstitialAdManager.resumeFrom(this);
        }

        FragmentTransaction transaction = getSupportFragmentManager().beginTransaction();
        transaction.hide(currentFragment);
        transaction.show(target);
        transaction.commit();
        currentFragment = target;
        return true;
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            // 新装用户首次打开时，从剪贴板读邀请码（来自邀请落地页），登录注册时自动绑定
            InviteCodeStore.tryReadFromClipboard(this);
        }
    }
}
