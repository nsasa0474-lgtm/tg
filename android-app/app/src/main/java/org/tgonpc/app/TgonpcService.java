package org.tgonpc.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import androidx.core.app.NotificationCompat;
import com.chaquo.python.android.AndroidPlatform;
import com.chaquo.python.Python;

/** Foreground-сервис: держит процесс и запускает Python SOCKS5. */
public class TgonpcService extends Service {
    public static final String ACTION_STOP = "org.tgonpc.app.STOP";
    private static final String CHANNEL_ID = "TGonPC_run";
    private static final int NOTIF_ID = 1;
    private volatile boolean bridgeStartRequested = false;
    private volatile boolean exitProbeRequested = false;
    private volatile long bridgeNotReadySince = 0L;
    private volatile long nextMtRescanAt = 0L;
    private volatile String lastProgress = "";

    private PowerManager.WakeLock wakeLock;

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            bridgeStartRequested = false;
            exitProbeRequested = false;
            stopBridgeAsync();
            TgonpcNetworkHelper.stop(getApplicationContext());
            releaseWakeLock();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                stopForeground(STOP_FOREGROUND_REMOVE);
            } else {
                stopForeground(true);
            }
            stopSelf();
            return START_NOT_STICKY;
        }

        acquireWakeLock();
        Notification n = buildNotification(getString(R.string.notif_running));
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            } else {
                startForeground(NOTIF_ID, n);
            }
        } catch (Exception e) {
            android.util.Log.e("TGonPC", "startForeground", e);
            try {
                startForeground(NOTIF_ID, n);
            } catch (Exception e2) {
                android.util.Log.e("TGonPC", "startForeground fallback", e2);
                stopSelf();
                return START_NOT_STICKY;
            }
        }
        TgonpcNetworkHelper.start(getApplicationContext());

        if (!bridgeStartRequested) {
            bridgeStartRequested = true;
            new Thread(this::startBridgeBlocking).start();
            new Thread(this::watchBridge, "TGonPC-watch").start();
        }
        return START_STICKY;
    }

    private void watchBridge() {
        while (bridgeStartRequested) {
            try {
                Thread.sleep(400);
                if (!bridgeStartRequested) {
                    break;
                }
                ensurePython();
                com.chaquo.python.PyObject mod = Python.getInstance().getModule("mobile_entry");
                boolean ready = mod.callAttr("is_bridge_ready").toBoolean();
                if (ready) {
                    bridgeNotReadySince = 0L;
                    syncMtProxyState(mod);
                    if (!exitProbeRequested) {
                        exitProbeRequested = true;
                        String batch = mod.callAttr("get_mtproxy_batch").toString();
                        if (batch != null && !batch.isEmpty()) {
                            TgonpcNetworkHelper.startMtProxyScan(
                                getApplicationContext(), batch, 4000
                            );
                            android.util.Log.i("TGonPC", "MTProxy scan started");
                        }
                    } else {
                        maybeRescanMtProxy(mod);
                    }
                    updateNotificationProgress();
                } else {
                    long now = System.currentTimeMillis();
                    if (bridgeNotReadySince == 0L) {
                        bridgeNotReadySince = now;
                    } else if (now - bridgeNotReadySince > 15000L) {
                        android.util.Log.w("TGonPC", "bridge not ready 15s, restart once");
                        bridgeNotReadySince = now;
                        exitProbeRequested = false;
                        new Thread(this::startBridgeBlocking, "TGonPC-restart").start();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                android.util.Log.w("TGonPC", "watchBridge", e);
            }
        }
    }

    private void maybeRescanMtProxy(com.chaquo.python.PyObject mod) {
        try {
            String found = TgonpcNetworkHelper.getMtProxyFound();
            if (found != null && !found.isEmpty()) {
                return;
            }
            if (TgonpcNetworkHelper.isMtProxyScanRunning()) {
                return;
            }
            String prog = TgonpcNetworkHelper.getMtProxyProgress();
            if (prog == null || !prog.contains("не найден")) {
                return;
            }
            long now = System.currentTimeMillis();
            if (now < nextMtRescanAt) {
                return;
            }
            nextMtRescanAt = now + 45000L;
            String batch = mod.callAttr("get_mtproxy_batch").toString();
            if (batch != null && !batch.isEmpty()) {
                TgonpcNetworkHelper.startMtProxyScan(getApplicationContext(), batch, 4000);
                android.util.Log.i("TGonPC", "MTProxy rescan");
            }
        } catch (Exception e) {
            android.util.Log.w("TGonPC", "mtproxy rescan", e);
        }
    }

    private void syncMtProxyState(com.chaquo.python.PyObject mod) {
        try {
            String found = TgonpcNetworkHelper.getMtProxyFound();
            if (found != null && !found.isEmpty()) {
                mod.callAttr("apply_mtproxy_found", found);
            }
            mod.callAttr("sync_from_java");
        } catch (Exception e) {
            android.util.Log.w("TGonPC", "syncMtProxy", e);
        }
    }

    private void updateNotificationProgress() {
        try {
            String prog = TgonpcNetworkHelper.getMtProxyProgress();
            if (prog == null || prog.isEmpty()) {
                ensurePython();
                prog = Python.getInstance().getModule("mobile_entry")
                    .callAttr("get_relay_progress").toString();
            }
            if (prog == null || prog.isEmpty() || "ok".equals(prog) || prog.equals(lastProgress)) {
                return;
            }
            lastProgress = prog;
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.notify(NOTIF_ID, buildNotification(prog));
            }
        } catch (Exception ignored) {
        }
    }

    private void startBridgeBlocking() {
        try {
            ensurePython();
            Python.getInstance().getModule("mobile_entry").callAttr("start_bridge_sync", 180.0);
        } catch (Exception e) {
            android.util.Log.e("TGonPC", "bridge start", e);
            bridgeStartRequested = false;
        }
    }

    private void ensurePython() {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(getApplicationContext()));
        }
    }

    private void stopBridgeAsync() {
        bridgeStartRequested = false;
        new Thread(() -> {
            try {
                ensurePython();
                Python.getInstance().getModule("mobile_entry").callAttr("stop_bridge");
            } catch (Exception ignored) {
            }
        }).start();
    }

    @Override
    public void onDestroy() {
        stopBridgeAsync();
        TgonpcNetworkHelper.stop(getApplicationContext());
        releaseWakeLock();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void acquireWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            return;
        }
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm == null) {
            return;
        }
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TGonPC::Bridge");
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire();
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        wakeLock = null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationChannel ch = new NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notif_channel),
            NotificationManager.IMPORTANCE_DEFAULT
        );
        ch.setDescription(getString(R.string.notif_running));
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) {
            nm.createNotificationChannel(ch);
        }
    }

    private Notification buildNotification(String progressText) {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(
            this, 0, open, PendingIntent.FLAG_IMMUTABLE
        );
        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(progressText)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(progressText))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build();
    }
}
