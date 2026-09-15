(function () {
  var mode = "login";
  var formEl = document.getElementById("auth-form");
  var webToken = (formEl && formEl.getAttribute("data-web-token")) || "";
  var $ = function (id) { return document.getElementById(id); };

  function applyMode(next) {
    mode = next || "login";
    document.querySelectorAll(".tab").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-tab") === mode);
    });
    var codeRow = $("code-row");
    if (codeRow) codeRow.hidden = mode !== "register";
    if ($("email-code")) $("email-code").required = mode === "register";
  }

  document.querySelectorAll(".tab").forEach(function (btn) {
    btn.addEventListener("click", function () {
      applyMode(btn.getAttribute("data-tab"));
    });
  });
  applyMode("login");

  var codeLeft = 0;
  var codeTimer = null;
  function tickCodeBtn() {
    var btn = $("btn-send-code");
    if (!btn) return;
    if (codeLeft <= 0) {
      btn.disabled = false;
      btn.textContent = "获取验证码";
      return;
    }
    btn.disabled = true;
    btn.textContent = codeLeft + "s";
    codeTimer = setTimeout(function () {
      codeLeft -= 1;
      tickCodeBtn();
    }, 1000);
  }

  if ($("btn-send-code")) {
    $("btn-send-code").addEventListener("click", function () {
      var email = $("email").value.trim();
      if (!email) return window.JKT.showMsg($("auth-msg"), false, "请先填写邮箱");
      window.JKT.api("/email/code", {
        method: "POST",
        headers: { "X-Web-Token": webToken },
        body: {
          email: email,
          event: "register",
          website: ($("website") && $("website").value) || "",
          web_token: webToken,
        },
      }).then(function (res) {
        if (!res.body.ok) return window.JKT.showMsg($("auth-msg"), false, res.body.error || "发送失败");
        window.JKT.showMsg($("auth-msg"), true, res.body.message || "验证码已发送");
        codeLeft = 60;
        if (codeTimer) clearTimeout(codeTimer);
        tickCodeBtn();
      }).catch(function () {
        window.JKT.showMsg($("auth-msg"), false, "网络错误");
      });
    });
  }

  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = $("email").value.trim();
    var password = $("password").value;
    var body = {
      email: email,
      password: password,
      website: ($("website") && $("website").value) || "",
      web_token: webToken,
    };
    var path = "/login";
    var headers = {};
    if (mode === "register") {
      path = "/register";
      body.code = ($("email-code") && $("email-code").value.trim()) || "";
      headers["X-Web-Token"] = webToken;
    }
    window.JKT.api(path, { method: "POST", headers: headers, body: body }).then(function (res) {
      if (!res.body.ok) return window.JKT.showMsg($("auth-msg"), false, res.body.error || "失败");
      window.JKT.showMsg($("auth-msg"), true, res.body.message || "成功");
      setTimeout(function () {
        location.href = "/workspace";
      }, 400);
    }).catch(function () {
      window.JKT.showMsg($("auth-msg"), false, "网络错误");
    });
  });
})();
