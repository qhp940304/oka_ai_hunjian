(function () {
  var $ = function (id) { return document.getElementById(id); };
  var imageUrls = [];
  var videoUrls = [];
  var pollTimer = null;

  function setLoggedIn() {
    if ($("guest-hint")) $("guest-hint").hidden = true;
    if ($("task-desc")) $("task-desc").hidden = false;
    if ($("task-body")) $("task-body").hidden = false;
    window.JKT.syncHeader(true);
  }

  function setLoggedOut() {
    if ($("guest-hint")) $("guest-hint").hidden = false;
    if ($("task-desc")) $("task-desc").hidden = true;
    if ($("task-body")) $("task-body").hidden = true;
    window.JKT.syncHeader(false);
  }

  function loadMe() {
    return window.JKT.api("/me").then(function (res) {
      if (res.body && res.body.ok) {
        setLoggedIn();
        return true;
      }
      setLoggedOut();
      return false;
    }).catch(function () {
      setLoggedOut();
      return false;
    });
  }

  document.querySelectorAll(".upload-trigger").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-for");
      var input = document.getElementById(id);
      if (input) input.click();
    });
  });

  function bindUpload(inputId, listId, kind, store) {
    var input = $(inputId);
    if (!input) return;
    input.addEventListener("change", function () {
      var files = Array.prototype.slice.call(input.files || []);
      if (!files.length) return;
      var fd = new FormData();
      files.forEach(function (f) { fd.append("files", f); });
      fd.append("kind", kind === "images" ? "image" : "video");
      window.JKT.showMsg($("task-msg"), true, "上传中…");
      window.JKT.api("/upload/materials", { method: "POST", body: fd }).then(function (res) {
        if (!res.body.ok) {
          return window.JKT.showMsg($("task-msg"), false, res.body.error || "上传失败");
        }
        var items = kind === "images" ? (res.body.images || []) : (res.body.videos || []);
        items.forEach(function (it) {
          if (it.url) store.push(it.url);
        });
        renderFileList(listId, store);
        window.JKT.showMsg($("task-msg"), true, "上传成功");
        input.value = "";
      }).catch(function () {
        window.JKT.showMsg($("task-msg"), false, "上传失败");
      });
    });
  }

  function renderFileList(listId, urls) {
    var ul = $(listId);
    if (!ul) return;
    ul.innerHTML = urls.map(function (u, i) {
      return "<li>#" + (i + 1) + " " + u.split("/").pop() + "</li>";
    }).join("");
  }

  bindUpload("images-file", "images-list", "images", imageUrls);
  bindUpload("videos-file", "videos-list", "videos", videoUrls);

  function pollQueue(jobId) {
    if (pollTimer) clearInterval(pollTimer);
    var box = $("queue-box");
    function tick() {
      window.JKT.api("/tasks/" + jobId).then(function (res) {
        if (!res.body.ok) return;
        var job = res.body.job || {};
        box.hidden = false;
        if (job.status === "pending" || job.status === "running") {
          box.textContent = job.queue_message || (job.status === "running" ? "正在生成…" : "排队中…");
        } else if (job.status === "success") {
          box.textContent = "生成完成，可前往「我的作品」下载";
          clearInterval(pollTimer);
        } else if (job.status === "failed") {
          box.textContent = "生成失败" + (job.error ? "：" + job.error : "");
          clearInterval(pollTimer);
        }
      });
    }
    tick();
    pollTimer = setInterval(tick, 5000);
  }

  if ($("btn-create")) {
    $("btn-create").addEventListener("click", function () {
      if (!imageUrls.length && !videoUrls.length) {
        return window.JKT.showMsg($("task-msg"), false, "请先上传图片或视频素材");
      }
      var boost = $("task-boost") && $("task-boost").checked;
      $("btn-create").disabled = true;
      window.JKT.api("/tasks", {
        method: "POST",
        body: { images: imageUrls, videos: videoUrls, boost: !!boost },
      }).then(function (res) {
        $("btn-create").disabled = false;
        if (!res.body.ok) {
          return window.JKT.showMsg($("task-msg"), false, res.body.error || "提交失败");
        }
        window.JKT.showMsg($("task-msg"), true, res.body.queue_message || "已提交");
        if (res.body.job_id) pollQueue(res.body.job_id);
        imageUrls = [];
        videoUrls = [];
        renderFileList("images-list", imageUrls);
        renderFileList("videos-list", videoUrls);
      }).catch(function () {
        $("btn-create").disabled = false;
        window.JKT.showMsg($("task-msg"), false, "网络错误");
      });
    });
  }

  loadMe();
})();
