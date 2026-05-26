package org.tgtunnel.app;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Build;
import android.util.Base64;
import android.util.Log;
import java.io.FileDescriptor;
import java.lang.reflect.Field;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SNIHostName;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.util.Collections;

/**
 * LTE: исходящие сокеты Python должны идти через мобильную сеть, а не «мёртвый» Wi‑Fi.
 * bindProcessToNetwork + bindSocket на каждый connect.
 */
public final class TunnelNetworkHelper extends ConnectivityManager.NetworkCallback {
    private static final String TAG = "TGTunnel";
    private static volatile ConnectivityManager sCm;
    private static volatile Network sNetwork;
    private static ConnectivityManager.NetworkCallback sCallback;
    private static ConnectivityManager.NetworkCallback sCellCallback;
    private static volatile Network sCellNetwork;

    private TunnelNetworkHelper() {
    }

    public static void start(Context context) {
        try {
            Context app = context.getApplicationContext();
            sCm = app.getSystemService(ConnectivityManager.class);
            if (sCm == null) {
                return;
            }
            stop(context);
            sCallback = new TunnelNetworkHelper();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                sCm.registerDefaultNetworkCallback(sCallback);
            } else {
                NetworkRequest req = new NetworkRequest.Builder()
                    .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    .build();
                sCm.registerNetworkCallback(req, sCallback);
            }
            registerCellularFallback();
            applyNetwork(pickBestNetwork());
        } catch (Exception e) {
            Log.w(TAG, "network helper start failed: " + e.getMessage());
            sCallback = null;
            sCellCallback = null;
            sNetwork = null;
            sCellNetwork = null;
        }
    }

    private static void registerCellularFallback() {
        if (sCm == null) {
            return;
        }
        NetworkRequest cellReq = new NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR)
            .build();
        sCellCallback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onAvailable(Network network) {
                sCellNetwork = network;
                Log.i(TAG, "cellular network: " + network);
                applyNetwork(pickBestNetwork());
            }

            @Override
            public void onLost(Network network) {
                if (network.equals(sCellNetwork)) {
                    sCellNetwork = null;
                    applyNetwork(pickBestNetwork());
                }
            }

            @Override
            public void onCapabilitiesChanged(Network network, NetworkCapabilities caps) {
                if (network.equals(sCellNetwork)) {
                    applyNetwork(pickBestNetwork());
                }
            }
        };
        try {
            sCm.registerNetworkCallback(cellReq, sCellCallback);
        } catch (Exception e) {
            Log.w(TAG, "cellular callback: " + e.getMessage());
            sCellCallback = null;
        }
    }

    public static void stop(Context context) {
        ConnectivityManager cm = context.getSystemService(ConnectivityManager.class);
        if (cm != null) {
            if (sCallback != null) {
                try {
                    cm.unregisterNetworkCallback(sCallback);
                } catch (Exception ignored) {
                }
            }
            if (sCellCallback != null) {
                try {
                    cm.unregisterNetworkCallback(sCellCallback);
                } catch (Exception ignored) {
                }
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                cm.bindProcessToNetwork(null);
            }
        }
        sCm = null;
        sCallback = null;
        sCellCallback = null;
        sNetwork = null;
        sCellNetwork = null;
    }

    /** Перед connect() из Python — обновить привязку к LTE/Wi‑Fi. */
    public static void refreshNetwork(Context context) {
        if (sCm == null) {
            sCm = context.getApplicationContext().getSystemService(ConnectivityManager.class);
        }
        applyNetwork(pickBestNetwork());
    }

    @Override
    public void onAvailable(Network network) {
        Log.i(TAG, "default network available: " + network);
        applyNetwork(pickBestNetwork());
    }

    @Override
    public void onLost(Network network) {
        Log.i(TAG, "default network lost: " + network);
        applyNetwork(pickBestNetwork());
    }

    @Override
    public void onCapabilitiesChanged(Network network, NetworkCapabilities networkCapabilities) {
        applyNetwork(pickBestNetwork());
    }

    private static Network pickBestNetwork() {
        ConnectivityManager cm = sCm;
        if (cm == null) {
            return null;
        }
        Network active = cm.getActiveNetwork();
        Network best = null;
        int bestScore = Integer.MIN_VALUE;

        Network[] networks = cm.getAllNetworks();
        if (networks.length == 0 && active != null) {
            networks = new Network[]{active};
        }

        for (Network n : networks) {
            int score = scoreNetwork(cm, n);
            if (score > bestScore) {
                bestScore = score;
                best = n;
            }
        }

        if (best == null && sCellNetwork != null) {
            best = sCellNetwork;
        }
        if (best == null) {
            best = active;
        }
        return best;
    }

    /** Выше = лучше. Cellular с интернетом побеждает Wi‑Fi без VALIDATED. */
    private static int scoreNetwork(ConnectivityManager cm, Network n) {
        if (n == null) {
            return Integer.MIN_VALUE;
        }
        NetworkCapabilities caps = cm.getNetworkCapabilities(n);
        if (caps == null || !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) {
            return Integer.MIN_VALUE;
        }
        int score = 0;
        if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
            score += 100;
        }
        if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_RESTRICTED)) {
            score += 10;
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
            score += 50;
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
            score += 70;
        }
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
            score += 60;
        }
        // Wi‑Fi без validated хуже LTE (типичный «висит на прокси» без интернета на Wi‑Fi)
        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            && !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
            score -= 200;
        }
        return score;
    }

    private static Network getOutboundNetwork() {
        Network best = pickBestNetwork();
        if (best != null) {
            return best;
        }
        if (sCellNetwork != null) {
            return sCellNetwork;
        }
        ConnectivityManager cm = sCm;
        if (cm != null) {
            return cm.getActiveNetwork();
        }
        return null;
    }

    private static void applyNetwork(Network network) {
        sNetwork = network;
        Log.i(TAG, "outbound network: " + network);
        // bindProcessToNetwork отключён — на части устройств ломает LTE для Chaquopy/Python
    }

    public static boolean bindSocketFd(int fd) {
        try {
            Network net = getOutboundNetwork();
            if (net == null) {
                return false;
            }
            net.bindSocket(fromInt(fd));
            return true;
        } catch (Exception e) {
            Log.w(TAG, "bindSocketFd failed: " + e.getMessage());
            return false;
        }
    }

    public static boolean bindSocketFdWithContext(Context context, int fd) {
        try {
            refreshNetwork(context);
            Network net = getOutboundNetwork();
            if (net == null) {
                return false;
            }
            net.bindSocket(fromInt(fd));
            return true;
        } catch (Exception e) {
            Log.w(TAG, "bindSocketFdWithContext: " + e.getMessage());
            return false;
        }
    }

    private static FileDescriptor fromInt(int fd) throws Exception {
        FileDescriptor fdesc = new FileDescriptor();
        Field field = FileDescriptor.class.getDeclaredField("descriptor");
        field.setAccessible(true);
        field.setInt(fdesc, fd);
        return fdesc;
    }

    /** TCP :443 через активную сеть (LTE). */
    public static boolean probeTcp(Context context, String host, int port, int timeoutMs) {
        Socket socket = null;
        try {
            refreshNetwork(context);
            Network net = getOutboundNetwork();
            if (net != null) {
                socket = net.getSocketFactory().createSocket();
            } else {
                socket = new Socket();
            }
            socket.connect(new InetSocketAddress(host, port), timeoutMs);
            return true;
        } catch (Exception e) {
            Log.d(TAG, "probeTcp " + host + ": " + e.getMessage());
            return false;
        } finally {
            if (socket != null) {
                try {
                    socket.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    private static final TrustManager[] TRUST_ALL = new TrustManager[] {
        new X509TrustManager() {
            @Override
            public void checkClientTrusted(X509Certificate[] chain, String authType) {
            }

            @Override
            public void checkServerTrusted(X509Certificate[] chain, String authType) {
            }

            @Override
            public X509Certificate[] getAcceptedIssuers() {
                return new X509Certificate[0];
            }
        }
    };

    /** TLS :443 + SNI (реальная проверка, TCP alone обманчив на LTE). */
    public static boolean probeTls(Context context, String ip, String sniHost, int timeoutMs) {
        Socket tcp = null;
        SSLSocket ssl = null;
        try {
            refreshNetwork(context);
            Network net = getOutboundNetwork();
            if (net != null) {
                tcp = net.getSocketFactory().createSocket();
            } else {
                tcp = new Socket();
            }
            tcp.connect(new InetSocketAddress(ip, 443), timeoutMs);
            tcp.setSoTimeout(timeoutMs);

            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(null, TRUST_ALL, new SecureRandom());
            ssl = (SSLSocket) sc.getSocketFactory().createSocket(tcp, ip, 443, true);
            SSLParameters params = ssl.getSSLParameters();
            params.setServerNames(Collections.singletonList(new SNIHostName(sniHost)));
            ssl.setSSLParameters(params);
            ssl.setSoTimeout(timeoutMs);
            ssl.startHandshake();
            Log.i(TAG, "probeTls OK " + ip + " sni=" + sniHost);
            return true;
        } catch (Exception e) {
            Log.d(TAG, "probeTls " + ip + ": " + e.getMessage());
            return false;
        } finally {
            if (ssl != null) {
                try {
                    ssl.close();
                } catch (Exception ignored) {
                }
            } else if (tcp != null) {
                try {
                    tcp.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    /**
     * Перебор всех relay: TLS+SNI (не останавливается на ложном TCP).
     * @return первый IP с успешным TLS или ""
     */
    public static String findWorkingRelayTls(
        Context context,
        String hostList,
        String sniHost,
        int timeoutMs
    ) {
        if (hostList == null || hostList.isEmpty()) {
            return "";
        }
        refreshNetwork(context);
        for (String raw : hostList.split(",")) {
            String ip = raw.trim();
            if (ip.isEmpty()) {
                continue;
            }
            if (probeTls(context, ip, sniHost, timeoutMs)) {
                Log.i(TAG, "findWorkingRelayTls: " + ip);
                return ip;
            }
        }
        return "";
    }

    /** TLS к hostname (прямой домен, не relay IP). */
    public static boolean probeTlsHost(Context context, String host, int timeoutMs) {
        return probeTls(context, host, host, timeoutMs);
    }

    /** Перебор доменов kws*.web.telegram.org на LTE. */
    public static String findWorkingDomain(Context context, String hostList, int timeoutMs) {
        if (hostList == null || hostList.isEmpty()) {
            return "";
        }
        refreshNetwork(context);
        for (String raw : hostList.split(",")) {
            String host = raw.trim();
            if (host.isEmpty()) {
                continue;
            }
            if (probeTlsHost(context, host, timeoutMs)) {
                Log.i(TAG, "findWorkingDomain: " + host);
                return host;
            }
        }
        return "";
    }

    /** Активная сеть — мобильная (или Wi‑Fi без интернета). */
    public static boolean isCellularPreferred(Context context) {
        try {
            refreshNetwork(context);
            ConnectivityManager cm = sCm;
            if (cm == null) {
                cm = context.getApplicationContext().getSystemService(ConnectivityManager.class);
            }
            if (cm == null) {
                return true;
            }
            Network active = cm.getActiveNetwork();
            if (active == null) {
                return true;
            }
            NetworkCapabilities caps = cm.getNetworkCapabilities(active);
            if (caps == null) {
                return true;
            }
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                return true;
            }
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                && !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) {
                return true;
            }
            return false;
        } catch (Exception e) {
            Log.w(TAG, "isCellularPreferred: " + e.getMessage());
            return true;
        }
    }

    /** @deprecated use findWorkingRelayTls */
    public static String findWorkingRelay(Context context, String hostList, int timeoutMs) {
        return findWorkingRelayTls(context, hostList, "kws2.web.telegram.org", timeoutMs);
    }

    private static byte[] decodeMtproxySecret(String secret) {
        if (secret == null || secret.isEmpty()) {
            return null;
        }
        String s = secret.trim().replace("-", "");
        try {
            if (s.startsWith("ee") || s.startsWith("dd")) {
                String payload = s.substring(2);
                if (payload.matches("^[0-9a-fA-F]+$") && payload.length() % 2 == 0) {
                    int len = payload.length();
                    byte[] out = new byte[len / 2];
                    for (int i = 0; i < len; i += 2) {
                        out[i / 2] = (byte) Integer.parseInt(payload.substring(i, i + 2), 16);
                    }
                    return out;
                }
                return Base64.decode(payload, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
            }
            if (s.length() == 32 && s.matches("^[0-9a-fA-F]+$")) {
                byte[] out = new byte[16];
                for (int i = 0; i < 32; i += 2) {
                    out[i / 2] = (byte) Integer.parseInt(s.substring(i, i + 2), 16);
                }
                return out;
            }
            if (s.matches("^[0-9a-fA-F]+$") && s.length() % 2 == 0) {
                int len = s.length();
                byte[] out = new byte[len / 2];
                for (int i = 0; i < len; i += 2) {
                    out[i / 2] = (byte) Integer.parseInt(s.substring(i, i + 2), 16);
                }
                return out;
            }
            return Base64.decode(s, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP);
        } catch (Exception e) {
            Log.d(TAG, "decodeMtproxySecret: " + e.getMessage());
            return null;
        }
    }

    /** strict: fake-TLS ≥80 байт; иначе ≥32. HTTP-ответы отбрасываем. */
    private static boolean isMtProxyHandshakeResponse(
        byte[] buf,
        int len,
        String secret,
        boolean strict
    ) {
        if (buf == null || len < (strict ? 40 : 20)) {
            return false;
        }
        if (buf[0] == 'H' || (len >= 4 && buf[0] == 'H' && buf[1] == 'T' && buf[2] == 'T' && buf[3] == 'P')) {
            return false;
        }
        String s = secret != null ? secret.trim().toLowerCase() : "";
        if (s.startsWith("ee") || s.startsWith("dd")) {
            if (buf[0] != 0x16) {
                return false;
            }
            return strict ? len >= 80 : len >= 32;
        }
        return strict ? len >= 40 : len >= 16;
    }

    private static boolean probeMtProxyMode(
        Context context,
        String host,
        int port,
        String secret,
        int timeoutMs,
        boolean strict
    ) {
        Socket socket = null;
        try {
            refreshNetwork(context);
            byte[] payload = decodeMtproxySecret(secret);
            if (payload == null || payload.length == 0) {
                return false;
            }
            Network net = getOutboundNetwork();
            if (net != null) {
                socket = net.getSocketFactory().createSocket();
            } else {
                socket = new Socket();
            }
            int connectMs = Math.max(1500, timeoutMs);
            int readMs = Math.max(1200, timeoutMs / 2);
            socket.connect(new InetSocketAddress(host, port), connectMs);
            socket.setSoTimeout(readMs);
            socket.getOutputStream().write(payload);
            socket.getOutputStream().flush();

            byte[] buf = new byte[512];
            int total = 0;
            int need = strict ? 80 : 32;
            long deadline = System.currentTimeMillis() + readMs + 500;
            while (total < need && System.currentTimeMillis() < deadline) {
                int left = (int) Math.min(readMs, deadline - System.currentTimeMillis());
                if (left <= 0) {
                    break;
                }
                socket.setSoTimeout(Math.max(200, left));
                int n = socket.getInputStream().read(buf, total, buf.length - total);
                if (n < 0) {
                    break;
                }
                if (n == 0) {
                    continue;
                }
                total += n;
            }
            if (!isMtProxyHandshakeResponse(buf, total, secret, strict)) {
                return false;
            }
            Log.i(TAG, "probeMtProxy OK " + host + ":" + port + " bytes=" + total + " strict=" + strict);
            return true;
        } catch (Exception e) {
            Log.d(TAG, "probeMtProxy " + host + ": " + e.getMessage());
            return false;
        } finally {
            if (socket != null) {
                try {
                    socket.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    /** MTProxy: TCP + secret + fake-TLS ответ. */
    public static boolean probeMtProxy(
        Context context,
        String host,
        int port,
        String secret,
        int timeoutMs
    ) {
        return probeMtProxyMode(context, host, port, secret, timeoutMs, true);
    }

    private static volatile String mtProgress = "";
    private static volatile String mtFound = "";
    private static volatile boolean mtScanRunning = false;
    private static Thread mtScanThread;

    public static String getMtProxyProgress() {
        String p = mtProgress;
        return p != null ? p : "";
    }

    /** host|port|secret или "" */
    public static String getMtProxyFound() {
        String f = mtFound;
        return f != null ? f : "";
    }

    public static boolean isMtProxyScanRunning() {
        return mtScanRunning;
    }

    /** Пакетный перебор MTProxy в Java-потоке. batch: host|port|secret построчно. */
    public static void startMtProxyScan(Context context, String batch, int timeoutMs) {
        if (batch == null || batch.isEmpty()) {
            mtProgress = "MTProxy: список пуст";
            return;
        }
        if (mtScanRunning) {
            return;
        }
        mtScanRunning = true;
        mtFound = "";
        mtProgress = "MTProxy…";
        final Context app = context.getApplicationContext();
        final String data = batch;
        final int tmo = Math.max(1500, timeoutMs);
        mtScanThread = new Thread(
            () -> {
                try {
                    refreshNetwork(app);
                    String[] lines = data.split("\n");
                    int total = 0;
                    for (String line : lines) {
                        if (line != null && !line.trim().isEmpty()) {
                            total++;
                        }
                    }
                    if (total == 0) {
                        mtProgress = "MTProxy: список пуст";
                        return;
                    }
                    int idx = 0;
                    for (int pass = 0; pass < 2 && mtFound.isEmpty(); pass++) {
                        final boolean strict = pass == 0;
                        idx = 0;
                        if (pass == 1) {
                            mtProgress = "MTProxy · повтор (мягче)…";
                        }
                        for (String raw : lines) {
                            if (Thread.interrupted() || !mtFound.isEmpty()) {
                                break;
                            }
                            String line = raw.trim();
                            if (line.isEmpty()) {
                                continue;
                            }
                            idx++;
                            String[] parts = line.split("\\|", 3);
                            if (parts.length < 3) {
                                continue;
                            }
                            String host = parts[0].trim();
                            int port;
                            try {
                                port = Integer.parseInt(parts[1].trim());
                            } catch (NumberFormatException e) {
                                continue;
                            }
                            String secret = parts[2].trim();
                            mtProgress = "MTProxy " + idx + "/" + total + " · " + host;
                            if (probeMtProxyMode(app, host, port, secret, tmo, strict)) {
                                mtFound = host + "|" + port + "|" + secret;
                                mtProgress = "MTProxy ✓ " + host;
                                break;
                            }
                        }
                    }
                    if (mtFound.isEmpty()) {
                        mtProgress = "не найден (MTProxy)";
                    }
                } catch (Exception e) {
                    Log.w(TAG, "mtproxy scan: " + e.getMessage());
                    mtProgress = "ошибка MTProxy";
                } finally {
                    mtScanRunning = false;
                }
            },
            "TGTunnel-MtScan"
        );
        mtScanThread.setDaemon(true);
        mtScanThread.start();
    }
}
