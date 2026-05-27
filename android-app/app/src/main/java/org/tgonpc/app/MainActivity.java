package org.tgonpc.app;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.chaquo.python.android.AndroidPlatform;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {
    private static final int REQ_NOTIF = 1001;
    private int socksPort = 1080;
    private static final String[] TELEGRAM_PACKAGES = {
        "org.telegram.messenger",
        "org.telegram.messenger.web",
        "org.thunderdog.challegram",
    };

    private TextView status;
    private Button toggle;
    private Button telegram;
    private boolean running = false;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Runnable statusPoller = new Runnable() {
        @Override
        public void run() {
            refreshStatusFromBridge();
            if (running) {
                handler.postDelayed(this, 400);
            }
        }
    };

    private void startStatusPolling() {
        handler.removeCallbacks(statusPoller);
        handler.post(statusPoller);
    }

    private void stopStatusPolling() {
        handler.removeCallbacks(statusPoller);
    }

    private void ensurePython() {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(getApplication()));
        }
    }

    private static boolean pyBool(PyObject value) {
        return value != null && value.toBoolean();
    }

    private static String pyStr(PyObject value) {
        return value == null ? "" : value.toString();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ensurePython();
        setContentView(R.layout.activity_main);

        status = findViewById(R.id.status);
        toggle = findViewById(R.id.toggle);
        telegram = findViewById(R.id.telegram);

        status.setText(R.string.status_loading);
        worker.execute(() -> {
            try {
                Python.getInstance().getModule("mobile_entry");
                runOnUiThread(() -> status.setText(R.string.status_idle));
            } catch (Exception e) {
                runOnUiThread(() -> status.setText(getString(R.string.status_error, e.getMessage())));
            }
        });

        toggle.setOnClickListener(v -> {
            if (running) {
                stopBridge();
            } else {
                startBridge();
            }
        });

        telegram.setOnClickListener(v -> openTelegramProxy());
    }

    private boolean hasNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return true;
        }
        return ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED;
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ActivityCompat.requestPermissions(
                this,
                new String[]{Manifest.permission.POST_NOTIFICATIONS},
                REQ_NOTIF
            );
        }
    }

    private void startTgonpcService() {
        Intent svc = new Intent(this, TgonpcService.class);
        ContextCompat.startForegroundService(this, svc);
    }

    private void stopTgonpcService() {
        Intent svc = new Intent(this, TgonpcService.class);
        svc.setAction(TgonpcService.ACTION_STOP);
        startService(svc);
    }

    private void startBridge() {
        if (!hasNotificationPermission()) {
            requestNotificationPermission();
            Toast.makeText(this, R.string.toast_allow_notif, Toast.LENGTH_LONG).show();
        }

        toggle.setEnabled(false);
        status.setText(R.string.status_starting);
        startTgonpcService();

        worker.execute(() -> {
            String err = "";
            boolean ok = false;
            try {
                PyObject mod = Python.getInstance().getModule("mobile_entry");
                for (int i = 0; i < 720; i++) {
                    if (pyBool(mod.callAttr("is_bridge_ready"))) {
                        ok = true;
                        break;
                    }
                    String e = pyStr(mod.callAttr("get_bridge_error"));
                    if (!e.isEmpty()) {
                        err = e;
                        break;
                    }
                    String prog = pyStr(mod.callAttr("get_relay_progress"));
                    if (!prog.isEmpty() && !"ok".equals(prog)) {
                        final String p = prog;
                        runOnUiThread(() -> status.setText(
                            getString(R.string.status_running_search, 1080, p)));
                    }
                    Thread.sleep(250);
                }
                if (!ok && err.isEmpty()) {
                    err = "SOCKS5 timeout (service)";
                }
            } catch (Exception e) {
                err = e.getMessage() != null ? e.getMessage() : e.toString();
            }
            final boolean success = ok;
            final String error = err;
            int portFinal = 1080;
            String relayFinal = "";
            boolean relayOkFinal = false;
            String progFinal = "";
            if (ok) {
                try {
                    PyObject mod2 = Python.getInstance().getModule("mobile_entry");
                    portFinal = mod2.callAttr("get_socks_port").toInt();
                    relayFinal = pyStr(mod2.callAttr("get_working_relay_ip"));
                    relayOkFinal = pyBool(mod2.callAttr("is_relay_verified"));
                    progFinal = pyStr(mod2.callAttr("get_relay_progress"));
                } catch (Exception ignored) {
                }
            }
            final int socksFinal = portFinal;
            final String relayStr = relayFinal;
            final boolean relayVerified = relayOkFinal;
            final String progressNow = progFinal;
            runOnUiThread(() -> {
                toggle.setEnabled(true);
                if (success) {
                    running = true;
                    socksPort = socksFinal;
                    toggle.setText(R.string.stop_bridge);
                    telegram.setEnabled(true);
                    updateRunningStatus(socksPort, relayStr, relayVerified, progressNow, "");
                    startStatusPolling();
                    Toast.makeText(this, R.string.toast_bridge_ok, Toast.LENGTH_SHORT).show();
                    maybeAskBatteryOptimization();
                } else {
                    stopTgonpcService();
                    status.setText(getString(R.string.status_error, error.isEmpty() ? "?" : error));
                    Toast.makeText(this, R.string.toast_bridge_fail, Toast.LENGTH_LONG).show();
                }
            });
        });
    }

    private void maybeAskBatteryOptimization() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            return;
        }
        try {
            android.os.PowerManager pm = (android.os.PowerManager) getSystemService(POWER_SERVICE);
            if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
                new AlertDialog.Builder(this)
                    .setTitle(R.string.battery_title)
                    .setMessage(R.string.battery_body)
                    .setPositiveButton(R.string.battery_open, (d, w) -> {
                        Intent i = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                        i.setData(Uri.parse("package:" + getPackageName()));
                        try {
                            startActivity(i);
                        } catch (ActivityNotFoundException ignored) {
                        }
                    })
                    .setNegativeButton(android.R.string.cancel, null)
                    .show();
            }
        } catch (Exception ignored) {
        }
    }

    private void stopBridge() {
        toggle.setEnabled(false);
        stopStatusPolling();
        stopTgonpcService();
        running = false;
        toggle.setText(R.string.start_bridge);
        toggle.setEnabled(true);
        telegram.setEnabled(false);
        status.setText(R.string.status_stopped);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatusFromBridge();
    }

    private void refreshStatusFromBridge() {
        if (!running) {
            return;
        }
        worker.execute(() -> {
            try {
                PyObject mod = Python.getInstance().getModule("mobile_entry");
                if (!pyBool(mod.callAttr("is_bridge_ready"))) {
                    return;
                }
                int port = mod.callAttr("get_socks_port").toInt();
                String relay = pyStr(mod.callAttr("get_working_relay_ip"));
                boolean relayOk = pyBool(mod.callAttr("is_relay_verified"));
                String progress = pyStr(mod.callAttr("get_relay_progress"));
                String exitMode = pyStr(mod.callAttr("get_exit_mode"));
                final int socks = port;
                final String relayIp = relay;
                final boolean verified = relayOk;
                final String prog = progress;
                final String mode = exitMode;
                runOnUiThread(() -> {
                    socksPort = socks;
                    toggle.setText(R.string.stop_bridge);
                    telegram.setEnabled(true);
                    updateRunningStatus(socks, relayIp, verified, prog, mode);
                });
            } catch (Exception ignored) {
            }
        });
    }

    private void updateRunningStatus(int port, String relay, boolean verified, String progress, String exitMode) {
        if (verified && !relay.isEmpty() && "mtproxy".equals(exitMode)) {
            status.setText(getString(R.string.status_running_mtproxy, port, relay));
        } else if (verified && !relay.isEmpty()) {
            status.setText(getString(R.string.status_running_relay, port, relay));
        } else if (progress != null && progress.startsWith("не найден")) {
            status.setText(getString(R.string.status_not_found, port, progress));
        } else if (progress != null && !progress.isEmpty() && !"ok".equals(progress)) {
            status.setText(getString(R.string.status_running_search, port, progress));
        } else if ("ожидание".equals(progress) || "инициализация".equals(progress)) {
            status.setText(getString(R.string.status_running_search, port, "запуск SOCKS…"));
        } else {
            status.setText(getString(R.string.status_running_port, port));
        }
    }

    private void openTelegramProxy() {
        if (!running) {
            Toast.makeText(this, R.string.toast_start_first, Toast.LENGTH_SHORT).show();
            return;
        }
        toggle.setEnabled(false);
        telegram.setEnabled(false);
        worker.execute(() -> {
            boolean ok = false;
            try {
                PyObject mod = Python.getInstance().getModule("mobile_entry");
                ok = pyBool(mod.callAttr("probe_socks5", 5.0));
            } catch (Exception ignored) {
            }
            final boolean probeOk = ok;
            runOnUiThread(() -> {
                toggle.setEnabled(true);
                if (!probeOk) {
                    telegram.setEnabled(true);
                    Toast.makeText(this, R.string.toast_proxy_dead, Toast.LENGTH_LONG).show();
                    status.setText(R.string.status_proxy_unreachable);
                    return;
                }
                telegram.setEnabled(true);
                Uri uri = Uri.parse("tg://socks?server=127.0.0.1&port=" + socksPort);
                openTelegramUri(uri.toString());
            });
        });
    }

    private void openTelegramUri(String uriString) {
        for (String pkg : TELEGRAM_PACKAGES) {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(uriString));
            intent.setPackage(pkg);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            try {
                startActivity(intent);
                return;
            } catch (ActivityNotFoundException ignored) {
            }
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(uriString))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (ActivityNotFoundException e) {
            showManualProxyDialog();
        }
    }

    private void showManualProxyDialog() {
        new AlertDialog.Builder(this)
            .setTitle(R.string.manual_proxy_title)
            .setMessage(getString(R.string.manual_proxy_body, socksPort))
            .setPositiveButton(android.R.string.ok, null)
            .show();
    }

    @Override
    protected void onDestroy() {
        worker.shutdown();
        super.onDestroy();
    }
}
