package com.mmtttt.jmcomicdemo;

import android.app.Activity;
import android.os.Bundle;
import android.os.Environment;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private EditText idInput;
    private Button downloadButton;
    private Button diagnosticsButton;
    private TextView output;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (16 * getResources().getDisplayMetrics().density);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("JMComic Android Demo");
        title.setTextSize(24);
        root.addView(title);

        TextView hint = new TextView(this);
        hint.setText(
                "输入 JM 本子 ID。下载目录使用 App 专属 Pictures/JMComic，不需要存储权限。\n" +
                "当前启用 Android 安全模式：章节并发=1、图片并发=1、最终保存为 PNG。\n" +
                "每个章节的图片目录中会生成 jmcomic_android.log，建议先点击环境自检。\n");
        root.addView(hint);

        idInput = new EditText(this);
        idInput.setHint("例如：438696");
        idInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        root.addView(idInput,
                new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT));

        diagnosticsButton = new Button(this);
        diagnosticsButton.setText("环境自检");
        diagnosticsButton.setOnClickListener(v -> runDiagnostics());
        root.addView(diagnosticsButton);

        downloadButton = new Button(this);
        downloadButton.setText("下载指定 ID 漫画");
        downloadButton.setOnClickListener(v -> startDownload());
        root.addView(downloadButton);

        output = new TextView(this);
        output.setTextIsSelectable(true);
        output.setText("等待操作…");

        ScrollView scroll = new ScrollView(this);
        scroll.addView(output);
        root.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f));

        setContentView(root);
    }

    private void setBusy(boolean busy) {
        downloadButton.setEnabled(!busy);
        diagnosticsButton.setEnabled(!busy);
    }

    private void runDiagnostics() {
        setBusy(true);
        output.setText("正在检查 Python / jmcomic / curl_cffi / Pillow / Android 资源状态…");

        executor.execute(() -> {
            String result;
            try {
                Python py = Python.getInstance();
                PyObject module = py.getModule("jm_bridge");
                result = module.callAttr("diagnostics").toString();
            } catch (Throwable t) {
                result = "Java/Chaquopy 调用失败:\n" + android.util.Log.getStackTraceString(t);
            }
            final String text = result;
            runOnUiThread(() -> {
                output.setText(text);
                setBusy(false);
            });
        });
    }

    private void startDownload() {
        String jmId = idInput.getText().toString().trim();
        if (jmId.isEmpty()) {
            output.setText("请先输入 JM ID。");
            return;
        }

        File pictures = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
        if (pictures == null) {
            output.setText("无法获取 App 外部文件目录。");
            return;
        }
        File targetDir = new File(pictures, "JMComic");

        setBusy(true);
        output.setText(
                "开始下载 JM" + jmId + "…\n" +
                "根目录: " + targetDir.getAbsolutePath() + "\n\n" +
                "Android 安全模式已启用：\n" +
                "- 章节并发: 1\n" +
                "- 图片并发: 1（jmcomic 桌面默认值为 30）\n" +
                "- WebP: Android BitmapFactory 解码\n" +
                "- 最终图片: PNG\n\n" +
                "诊断日志会持续写入实际图片目录中的 jmcomic_android.log。\n" +
                "在 Python 下载函数返回前，界面不会逐条刷新，请以日志文件和已落盘图片为准。"
        );

        executor.execute(() -> {
            String result;
            try {
                Python py = Python.getInstance();
                PyObject module = py.getModule("jm_bridge");
                result = module.callAttr(
                        "download_album_by_id",
                        jmId,
                        targetDir.getAbsolutePath()
                ).toString();
            } catch (Throwable t) {
                result = "Java/Chaquopy 调用失败:\n" + android.util.Log.getStackTraceString(t);
            }

            final String text = result;
            runOnUiThread(() -> {
                output.setText(text);
                setBusy(false);
            });
        });
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
