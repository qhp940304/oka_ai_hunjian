(function () {
  function api(path, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    if (!(opts.body instanceof FormData)) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    return fetch("/api/v1" + path, {
      method: opts.method || "GET",
      credentials: "same-origin",
      headers: headers,
      body: opts.body
        ? (opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body))
        : undefined,
    }).then(function (r) {
      return r.json().then(function (j) {
        return { status: r.status, body: j };
      });
    });
  }

  function showMsg(el, ok, text) {
    if (!el) return;
    el.className = "msg show " + (ok ? "ok" : "err");
    el.textContent = text || "";
  }

  function syncHeader(loggedIn) {
    var login = document.getElementById("nav-login");
    var logout = document.getElementById("nav-logout");
    if (loggedIn) {
      if (login) {
        login.hidden = true;
        login.setAttribute("aria-hidden", "true");
      }
      if (logout) {
        logout.hidden = false;
        logout.removeAttribute("aria-hidden");
      }
    } else {
      if (login) {
        login.hidden = false;
        login.removeAttribute("aria-hidden");
        login.textContent = "登录";
        login.href = "/login";
      }
      if (logout) {
        logout.hidden = true;
        logout.setAttribute("aria-hidden", "true");
      }
    }
  }

  function refreshAuthHint() {
    return api("/me").then(function (res) {
      var ok = res.body && res.body.ok;
      syncHeader(!!ok);
      return ok ? res.body : null;
    }).catch(function () {
      syncHeader(false);
      return null;
    });
  }

  var logoutBtn = document.getElementById("nav-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      api("/logout", { method: "POST", body: {} }).then(function () {
        syncHeader(false);
        location.href = "/login";
      });
    });
  }

  window.JKT = {
    api: api,
    showMsg: showMsg,
    syncHeader: syncHeader,
    refreshAuthHint: refreshAuthHint,
  };

  refreshAuthHint();
})();
