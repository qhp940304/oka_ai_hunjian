(function () {
  var $ = function (id) { return document.getElementById(id); };
  var timer = null;

  function statusLabel(s) {
    return ({ pending: "排队中", running: "生成中", success: "已完成", failed: "失败" })[s] || s;
  }

  function render(tasks) {
    var list = $("task-list");
    var filter = ($("status-filter") && $("status-filter").value) || "";
    var rows = (tasks || []).filter(function (t) {
      return !filter || t.status === filter;
    });
    $("tasks-empty").hidden = rows.length > 0;
    list.innerHTML = rows.map(function (t) {
      var downloads = "";
      if (t.download_urls && t.download_urls.length) {
        downloads = t.download_urls.map(function (u, i) {
          return '<a class="btn btn-primary" href="' + u + '">下载成片 ' + (i + 1) + "</a>";
        }).join(" ");
      } else if (t.expired) {
        downloads = '<span class="muted">成片已过期</span>';
      } else if (t.status === "pending" || t.status === "running") {
        downloads = '<span class="muted">' + (t.queue_message || "处理中…") + "</span>";
      } else if (t.status === "failed") {
        downloads = '<span class="muted">生成失败</span>';
      }
      return (
        '<li class="task-item">' +
          '<div class="row">' +
            "<strong>" + t.job_id + "</strong>" +
            '<span class="badge ' + t.status + '">' + statusLabel(t.status) + "</span>" +
          "</div>" +
          '<div class="muted">创建于 ' + (t.created_at || "-") +
            (t.boost ? " · 加速" : "") +
          "</div>" +
          '<div class="row">' + downloads + "</div>" +
        "</li>"
      );
    }).join("");
  }

  function load() {
    return window.JKT.api("/tasks?limit=50").then(function (res) {
      if (res.status === 401) {
        $("login-hint").hidden = false;
        $("tasks-empty").hidden = true;
        $("task-list").innerHTML = "";
        return;
      }
      $("login-hint").hidden = true;
      if (!res.body.ok) {
        window.JKT.showMsg($("tasks-msg"), false, res.body.error || "加载失败");
        return;
      }
      render(res.body.tasks || []);
    }).catch(function () {
      window.JKT.showMsg($("tasks-msg"), false, "网络错误");
    });
  }

  if ($("btn-reload")) $("btn-reload").addEventListener("click", load);
  if ($("status-filter")) $("status-filter").addEventListener("change", load);

  load();
  timer = setInterval(load, 8000);
})();
