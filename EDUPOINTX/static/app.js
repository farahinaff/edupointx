const appRoot = document.getElementById("appRoot");
const state = {
  user: JSON.parse(localStorage.getItem("edupointx-user") || "null"),
  page: "welcome",
  signupRole: null,
  classes: [],
  studentTab: "info",
  teacherTab: "add",
  adminTab: "class-view",
  teacherClass: null,
  adminClass: null,
  adminRedemptionStatus: "pending",
};

const deedCategories = ["Discipline", "Academics", "Sports", "Leadership", "Other"];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.detail || "Something went wrong.");
  return data;
}

function setUser(user) {
  state.user = user;
  localStorage.setItem("edupointx-user", JSON.stringify(user));
}

function logout() {
  state.user = null;
  localStorage.removeItem("edupointx-user");
  state.page = "welcome";
  render();
}

function setPage(page) {
  state.page = page;
  render();
}

function message(text = "", kind = "") {
  return `<p class="message ${kind}">${escapeHtml(text)}</p>`;
}

function renderBars(items, labelKey, valueKey) {
  if (!items.length) return `<p class="meta">No data yet.</p>`;
  const max = Math.max(...items.map((item) => Number(item[valueKey]) || 0), 1);
  return `<div class="chart">${items
    .map((item) => {
      const value = Number(item[valueKey]) || 0;
      const width = Math.max((value / max) * 100, value ? 6 : 0);
      return `<div class="bar-row">
        <span>${escapeHtml(item[labelKey])}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
        <strong>${value}</strong>
      </div>`;
    })
    .join("")}</div>`;
}

function renderLine(items, valueKey) {
  if (!items.length) return `<p class="meta">No trend data yet.</p>`;
  const max = Math.max(...items.map((item) => Number(item[valueKey]) || 0), 1);
  return `<div class="line-chart">${items
    .map((item) => {
      const value = Number(item[valueKey]) || 0;
      const height = Math.max((value / max) * 140, value ? 12 : 0);
      return `<div class="line-col">
        <div class="line-bar" style="height:${height}px"></div>
        <small>${escapeHtml(String(item.date).slice(5))}</small>
        <strong>${value}</strong>
      </div>`;
    })
    .join("")}</div>`;
}

async function loadClasses() {
  try {
    state.classes = await api("/api/classes");
  } catch (_error) {
    state.classes = [];
  }
}

function renderTabs(items, active, prefix) {
  return `<div class="tabs">${items
    .map(
      (item) =>
        `<button class="tab ${active === item.id ? "active" : ""}" data-${prefix}-tab="${item.id}">${escapeHtml(
          item.label
        )}</button>`
    )
    .join("")}</div>`;
}

function bindTabs(attr, setter) {
  document.querySelectorAll(`[data-${attr}-tab]`).forEach((button) => {
    button.addEventListener("click", async () => {
      setter(button.dataset[`${attr}Tab`]);
      await render();
    });
  });
}

function renderWelcome() {
  appRoot.innerHTML = `
    <div class="stack">
      <button id="loginStart">Login</button>
      <button id="signupStart">Sign Up</button>
    </div>
  `;
  document.getElementById("loginStart").addEventListener("click", () => setPage("select_role_login"));
  document.getElementById("signupStart").addEventListener("click", () => setPage("select_role_signup"));
}

function renderRoleSelection(mode) {
  appRoot.innerHTML = `
    <div class="stack">
      <h3>${mode === "login" ? "Login as..." : "Sign Up as..."}</h3>
      <button id="studentRole">Student</button>
      <button id="teacherRole">Teacher</button>
      <button id="backHome">Back</button>
    </div>
  `;
  document.getElementById("studentRole").addEventListener("click", () => {
    if (mode === "login") setPage("login_student");
    else {
      state.signupRole = "student";
      setPage("signup");
    }
  });
  document.getElementById("teacherRole").addEventListener("click", () => {
    if (mode === "login") setPage("login_teacher");
    else {
      state.signupRole = "teacher";
      setPage("signup");
    }
  });
  document.getElementById("backHome").addEventListener("click", () => setPage("welcome"));
}

function renderLogin(role) {
  const allowedRoles = role === "student" ? ["student"] : ["teacher", "admin"];
  appRoot.innerHTML = `
    <form class="stack" id="loginForm">
      <h3>Login as ${role === "student" ? "Student" : "Teacher"}</h3>
      <label>Username<input name="username" required /></label>
      <label>Password<input type="password" name="password" required /></label>
      <button type="submit">Login</button>
      <button type="button" id="backButton">Back</button>
      ${message("", "")}
    </form>
  `;
  const form = document.getElementById("loginForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    try {
      const user = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      });
      if (!allowedRoles.includes(user.role)) throw new Error(`Invalid ${role} credentials.`);
      setUser(user);
      await render();
    } catch (error) {
      form.querySelector(".message").outerHTML = message(error.message, "error");
    }
  });
  document.getElementById("backButton").addEventListener("click", () => setPage("welcome"));
}

function renderSignup() {
  appRoot.innerHTML = `
    <form class="stack" id="signupForm">
      <h3>Sign Up as ${escapeHtml(state.signupRole || "")}</h3>
      <label>Username<input name="username" required /></label>
      <label>Full Name<input name="full_name" required /></label>
      <label>Gender
        <select name="gender">
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
      </label>
      <label>Password<input type="password" name="password" required /></label>
      <label>Confirm Password<input type="password" name="confirm" required /></label>
      ${state.signupRole === "student" ? `<label>Select Class<select name="class_name">${(state.classes.length ? state.classes : ["1 Bestari"])
        .map((className) => `<option value="${escapeHtml(className)}">${escapeHtml(className)}</option>`)
        .join("")}</select></label>` : ""}
      <button type="submit">Create Account</button>
      <button type="button" id="backButton">Back</button>
      ${message("", "")}
    </form>
  `;
  const form = document.getElementById("signupForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    if (formData.get("password") !== formData.get("confirm")) {
      form.querySelector(".message").outerHTML = message("Passwords do not match.", "error");
      return;
    }
    try {
      const user = await api("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          username: formData.get("username"),
          full_name: formData.get("full_name"),
          gender: formData.get("gender"),
          password: formData.get("password"),
          role: state.signupRole,
          class_name: state.signupRole === "student" ? formData.get("class_name") : null,
        }),
      });
      setUser(user);
      await render();
    } catch (error) {
      form.querySelector(".message").outerHTML = message(error.message, "error");
    }
  });
  document.getElementById("backButton").addEventListener("click", () => setPage("select_role_signup"));
}

function renderStudentSection(data) {
  if (state.studentTab === "info") {
    return `<div class="card-grid">
      <article class="card">
        <h4>Student Info</h4>
        <p class="meta">Name: ${escapeHtml(data.student.name)}</p>
        <p class="meta">Gender: ${escapeHtml(data.student.gender || "-")}</p>
        <p class="meta">Class: ${escapeHtml(data.student.class_name)}</p>
        <p class="meta">Total Points: ${data.student.total_points}</p>
      </article>
      <article class="card"><h4>Points</h4><div class="metric">${data.student.total_points}</div></article>
    </div>`;
  }
  if (state.studentTab === "rewards") {
    return `<article class="card"><h4>Available Rewards</h4><div class="list">${data.rewards
      .map(
        (reward) => `<div class="list-item">
          <div class="row"><strong>${escapeHtml(reward.name)}</strong><span class="pill">${reward.cost} pts</span></div>
          <p class="meta">${escapeHtml(reward.description)}</p>
          <p class="meta">Stock: ${reward.stock} | Source: ${escapeHtml(reward.source)}</p>
          <button data-redeem="${reward.id}">Request Redemption</button>
        </div>`
      )
      .join("")}</div>${message("", "")}</article>`;
  }
  if (state.studentTab === "transactions") {
    return `<article class="card"><h4>Redemption History</h4>${data.redemptions.length ? `<table class="table"><thead><tr><th>Reward</th><th>Status</th><th>Date</th></tr></thead><tbody>${data.redemptions
      .map((row) => `<tr><td>${escapeHtml(row.reward)}</td><td>${escapeHtml(row.status)}</td><td>${escapeHtml(
        new Date(row.date).toLocaleString()
      )}</td></tr>`)
      .join("")}</tbody></table>` : `<p class="meta">No redemptions yet.</p>`}</article>`;
  }
  if (state.studentTab === "activities") {
    return `<div class="card-grid">
      <article class="card"><h4>Activity Log</h4>${data.activities.length ? `<table class="table"><thead><tr><th>Category</th><th>Reason</th><th>Points</th><th>Date</th></tr></thead><tbody>${data.activities
        .map((row) => `<tr><td>${escapeHtml(row.category)}</td><td>${escapeHtml(row.reason)}</td><td>${row.points}</td><td>${escapeHtml(
          new Date(row.date).toLocaleString()
        )}</td></tr>`)
        .join("")}</tbody></table>` : `<p class="meta">No activity records yet.</p>`}</article>
      <article class="card"><h4>Point Trend</h4>${renderLine(data.trend, "points")}</article>
    </div>`;
  }
  return `<article class="card"><h4>Leaderboard: ${escapeHtml(data.student.class_name)}</h4>${data.leaderboard.length ? renderBars(data.leaderboard, "student_name", "live_points") : `<p class="meta">No other students in your class yet.</p>`}</article>`;
}

async function renderStudentDashboard() {
  const data = await api(`/api/students/${state.user.student_id}/dashboard`);
  appRoot.innerHTML = `
    <div class="dashboard-top">
      <div>
        <h2>Student Dashboard</h2>
        <p class="meta">Logged in as ${escapeHtml(state.user.username)} (${escapeHtml(state.user.role)})</p>
      </div>
      <button id="logoutButton">Logout</button>
    </div>
    ${renderTabs(
      [
        { id: "info", label: "Info" },
        { id: "rewards", label: "Rewards" },
        { id: "transactions", label: "Transactions" },
        { id: "activities", label: "Activities" },
        { id: "leaderboard", label: "Leaderboard" },
      ],
      state.studentTab,
      "student"
    )}
    ${renderStudentSection(data)}
  `;
  document.getElementById("logoutButton").addEventListener("click", logout);
  bindTabs("student", (value) => {
    state.studentTab = value;
  });
  document.querySelectorAll("[data-redeem]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await api("/api/redemptions/request", {
          method: "POST",
          body: JSON.stringify({
            student_id: state.user.student_id,
            reward_id: Number(button.dataset.redeem),
          }),
        });
        state.studentTab = "transactions";
        await render();
      } catch (error) {
        const msgNode = appRoot.querySelector(".message");
        if (msgNode) msgNode.outerHTML = message(error.message, "error");
      }
    });
  });
}

function renderTeacherTab(data) {
  if (state.teacherTab === "add") {
    return `<div class="card-grid">
      <article class="card">
        <h4>Add Student Points</h4>
        <form class="stack" id="teacherAddForm">
          <div class="field-group">
            <span class="field-label">Select Students</span>
            <label class="check-row select-all">
              <input type="checkbox" id="selectAllStudents" />
              <span>All students in ${escapeHtml(data.class_name)}</span>
            </label>
            <div class="check-list">${data.students.length ? data.students
              .map(
                (student) => `<label class="check-row">
                  <input type="checkbox" name="student_ids" value="${student.id}" />
                  <span>${escapeHtml(student.name)}</span>
                </label>`
              )
              .join("") : `<p class="meta">No students found in this class.</p>`}</div>
          </div>
          <label>Deed Category<select name="category">${deedCategories
            .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
            .join("")}</select></label>
          <label>Reason / Description<input name="reason" required /></label>
          <label>Point Reward<input name="points" type="number" min="1" max="100" value="10" required /></label>
          <button type="submit" ${data.students.length ? "" : "disabled"}>Submit</button>
          ${message("", "")}
        </form>
      </article>
      <article class="card">
        <h4>Students in ${escapeHtml(data.class_name)}</h4>
        <div class="list">${data.students
          .map((student) => `<div class="list-item">${escapeHtml(student.name)}</div>`)
          .join("")}</div>
      </article>
    </div>`;
  }
  if (state.teacherTab === "qr") {
    return `<article class="card">
      <h4>Upload QR to Add Points</h4>
      <form class="stack" id="qrUploadForm">
        <label>Upload QR image<input type="file" name="qr_image" accept=".png,.jpg,.jpeg" required /></label>
        <button type="submit">Scan QR Image</button>
        ${message("", "")}
      </form>
      <div id="qrStudentResult"></div>
      <p class="meta">Direct QR links like <span class="pill">?action=addpoints&amp;sid=1</span> still work too.</p>
    </article>`;
  }
  if (state.teacherTab === "insights") {
    return `<article class="card"><h4>Class Performance Insights</h4>${renderBars(data.class_points, "name", "points")}</article>`;
  }
  if (state.teacherTab === "categories") {
    return `<article class="card"><h4>Top Categories</h4>${data.categories.length ? `<table class="table"><thead><tr><th>Category</th><th>Activity Count</th><th>Total Points</th></tr></thead><tbody>${data.categories
      .map((item) => `<tr><td>${escapeHtml(item.category)}</td><td>${item.count}</td><td>${item.total_points}</td></tr>`)
      .join("")}</tbody></table>` : `<p class="meta">No data yet for this class.</p>`}</article>`;
  }
  return `<div class="card-grid">
    <article class="card"><h4>Top 3 Students</h4>${renderBars(data.top3, "student_name", "live_points")}</article>
    <article class="card"><h4>Bottom 3 Students</h4>${renderBars(data.bottom3, "student_name", "live_points")}</article>
  </div>`;
}

async function renderTeacherDashboard() {
  const classes = await api(`/api/teachers/${state.user.teacher_id}/classes`);
  if (!classes.length && state.user.role !== "admin") {
    appRoot.innerHTML = `<div class="dashboard-top"><div><h2>Teacher Dashboard</h2><p class="meta">No classes assigned.</p></div><button id="logoutButton">Logout</button></div><article class="card"><p class="meta">Ask an admin to assign a class before adding activities.</p></article>`;
    document.getElementById("logoutButton").addEventListener("click", logout);
    return;
  }
  if (!state.teacherClass || !classes.includes(state.teacherClass)) state.teacherClass = classes[0];
  const data = await api(`/api/teachers/${state.user.teacher_id}/dashboard?class_name=${encodeURIComponent(state.teacherClass)}`);
  appRoot.innerHTML = `
    <div class="dashboard-top">
      <div>
        <h2>${state.user.role === "admin" ? "Admin View: Class Deeds" : "Teacher Dashboard"}</h2>
        <p class="meta">Logged in as ${escapeHtml(state.user.username)} (${escapeHtml(state.user.role)})</p>
      </div>
      <div class="inline-actions">
        <select id="teacherClass">${classes.map((className) => `<option value="${escapeHtml(className)}" ${className === state.teacherClass ? "selected" : ""}>${escapeHtml(className)}</option>`).join("")}</select>
        <button id="logoutButton">Logout</button>
      </div>
    </div>
    ${renderTabs(
      [
        { id: "add", label: "Add Points" },
        { id: "qr", label: "Upload QR to Add Points" },
        { id: "insights", label: "Class Insights" },
        { id: "categories", label: "Top Categories" },
        { id: "rankings", label: "Student Rankings" },
      ],
      state.teacherTab,
      "teacher"
    )}
    ${renderTeacherTab(data)}
    ${state.user.role === "admin" ? `<div id="adminArea"></div>` : ""}
  `;
  document.getElementById("logoutButton").addEventListener("click", logout);
  document.getElementById("teacherClass").addEventListener("change", async (event) => {
    state.teacherClass = event.target.value;
    await render();
  });
  bindTabs("teacher", (value) => {
    state.teacherTab = value;
  });
  const addForm = document.getElementById("teacherAddForm");
  if (addForm) {
    const studentCheckboxes = Array.from(addForm.querySelectorAll("[name='student_ids']"));
    const selectAll = document.getElementById("selectAllStudents");
    selectAll?.addEventListener("change", () => {
      selectAll.indeterminate = false;
      studentCheckboxes.forEach((checkbox) => {
        checkbox.checked = selectAll.checked;
      });
    });
    studentCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const checkedCount = studentCheckboxes.filter((item) => item.checked).length;
        if (selectAll) {
          selectAll.checked = studentCheckboxes.length > 0 && checkedCount === studentCheckboxes.length;
          selectAll.indeterminate = checkedCount > 0 && checkedCount < studentCheckboxes.length;
        }
      });
    });
    addForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(addForm);
      const studentIds = formData.getAll("student_ids").map(Number).filter(Boolean);
      try {
        if (!studentIds.length) throw new Error("Select at least one student.");
        await api(`/api/teachers/${state.user.teacher_id}/activities/bulk`, {
          method: "POST",
          body: JSON.stringify({
            student_ids: studentIds,
            category: formData.get("category"),
            reason: formData.get("reason"),
            points: Number(formData.get("points")),
          }),
        });
        await render();
      } catch (error) {
        addForm.querySelector(".message").outerHTML = message(error.message, "error");
      }
    });
  }
  const qrUploadForm = document.getElementById("qrUploadForm");
  if (qrUploadForm) {
    qrUploadForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(qrUploadForm);
      const image = formData.get("qr_image");
      if (!(image instanceof File) || !image.size) return;
      const upload = new FormData();
      upload.append("file", image);
      try {
        const response = await fetch("/api/qr/decode", { method: "POST", body: upload });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to decode QR image.");
        if (data.action === "redeem") {
          document.getElementById("qrStudentResult").innerHTML = `
            <div class="stack">
              <h3>Redeem Rewards for ${escapeHtml(data.name)}</h3>
              <p class="meta">Class: ${escapeHtml(data.class_name)}</p>
              <div id="qrRedeemContent"></div>
            </div>
          `;
          const redeemRoot = document.getElementById("qrRedeemContent");
          const dashboard = await api(`/api/students/${data.student_id}/dashboard`);
          if (!dashboard.rewards.length) {
            redeemRoot.innerHTML = `<p class="meta">No rewards available right now.</p>`;
          } else {
            redeemRoot.innerHTML = `
              <div class="list">${dashboard.rewards
                .map(
                  (reward) => `<div class="list-item">
                    <div class="row"><strong>${escapeHtml(reward.name)}</strong><span class="pill">${reward.cost} pts</span></div>
                    <p class="meta">${escapeHtml(reward.description)}</p>
                    <button data-qr-redeem="${reward.id}">Request Redemption</button>
                  </div>`
                )
                .join("")}</div>
              ${message("", "")}
            `;
            redeemRoot.querySelectorAll("[data-qr-redeem]").forEach((button) => {
              button.addEventListener("click", async () => {
                try {
                  await api("/api/redemptions/request", {
                    method: "POST",
                    body: JSON.stringify({
                      student_id: data.student_id,
                      reward_id: Number(button.dataset.qrRedeem),
                    }),
                  });
                  redeemRoot.querySelector(".message").outerHTML = message("Request submitted. An admin will review it shortly.", "success");
                } catch (error) {
                  redeemRoot.querySelector(".message").outerHTML = message(error.message, "error");
                }
              });
            });
          }
        } else {
          document.getElementById("qrStudentResult").innerHTML = `
            <form class="stack" id="qrDecodedAddForm">
              <p class="meta">Student: ${escapeHtml(data.name)} (${escapeHtml(data.class_name)})</p>
              <input type="hidden" name="student_id" value="${data.student_id}" />
              <label>Deed Category<select name="category">${deedCategories
                .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
                .join("")}</select></label>
              <label>Reason / Description<input name="reason" required /></label>
              <label>Point Reward<input name="points" type="number" min="1" max="100" value="10" required /></label>
              <button type="submit">Add Points</button>
              ${message("", "")}
            </form>
          `;
          document.getElementById("qrDecodedAddForm").addEventListener("submit", async (submitEvent) => {
            submitEvent.preventDefault();
            const decodedForm = new FormData(submitEvent.target);
            try {
              await api(`/api/teachers/${state.user.teacher_id}/activities`, {
                method: "POST",
                body: JSON.stringify({
                  student_id: Number(decodedForm.get("student_id")),
                  category: decodedForm.get("category"),
                  reason: decodedForm.get("reason"),
                  points: Number(decodedForm.get("points")),
                }),
              });
              await render();
            } catch (error) {
              submitEvent.target.querySelector(".message").outerHTML = message(error.message, "error");
            }
          });
        }
      } catch (error) {
        qrUploadForm.querySelector(".message").outerHTML = message(error.message, "error");
      }
    });
  }
  if (state.user.role === "admin") await renderAdminArea();
}

function adminTabs() {
  return [
    { id: "class-view", label: "Class View" },
    { id: "teacher-assignment", label: "Teacher Assignment" },
    { id: "manage-stocks", label: "Manage Stocks" },
    { id: "stock-approvals", label: "Stock Approvals" },
    { id: "point-transactions", label: "Point Transactions" },
    { id: "redemption-insights", label: "Redemption Insights" },
    { id: "reset-password", label: "Reset Password" },
  ];
}

function renderAdminContent(data) {
  if (state.adminTab === "class-view") {
    return `<div class="card-grid">
      <article class="card"><h4>Students in Class</h4>${data.class_view.students.length ? `<table class="table"><thead><tr><th>ID</th><th>Name</th><th>Points</th></tr></thead><tbody>${data.class_view.students.map((student) => `<tr><td>${student.id}</td><td>${escapeHtml(student.name)}</td><td>${student.points}</td></tr>`).join("")}</tbody></table>` : `<p class="meta">No students found in this class.</p>`}</article>
      <article class="card"><h4>Teachers assigned to this class</h4>${data.class_view.teachers.length ? `<div class="list">${data.class_view.teachers.map((teacher) => `<div class="list-item">${escapeHtml(teacher)}</div>`).join("")}</div>` : `<p class="meta">No teachers assigned yet.</p>`}</article>
    </div>`;
  }
  if (state.adminTab === "teacher-assignment") {
    return `<article class="card"><h4>Assign / Unassign Teachers</h4><div class="list">${data.teacher_assignment.teachers.map((teacher) => `<div class="list-item">
      <div class="row"><strong>${escapeHtml(teacher.name)}</strong><button data-assign-teacher="${teacher.id}" data-assign-state="${teacher.assigned_to_selected_class ? "off" : "on"}">${teacher.assigned_to_selected_class ? "Unassign" : "Assign"}</button></div>
      <p class="meta">Classes: ${escapeHtml(teacher.classes.join(", ") || "None")}</p>
    </div>`).join("")}</div></article>`;
  }
  if (state.adminTab === "manage-stocks") {
    return `<div class="card-grid">
      <article class="card">
        <h4>Manage Rewards</h4>
        <div class="list">${data.rewards.map((reward) => `<div class="list-item">
          <div class="row"><strong>${escapeHtml(reward.name)}</strong><span class="pill">${reward.stock} stock</span></div>
          <p class="meta">${reward.cost} pts | ${escapeHtml(reward.source)}</p>
          <form class="stack reward-edit" data-reward-id="${reward.id}">
            <label>New Cost<input type="number" name="cost" value="${reward.cost}" min="1" /></label>
            <label>New Stock<input type="number" name="stock" value="${reward.stock}" min="0" /></label>
            <div class="inline-actions">
              <button type="submit">Update</button>
              <button type="button" data-delete-reward="${reward.id}">Delete</button>
            </div>
          </form>
        </div>`).join("")}</div>
      </article>
      <article class="card">
        <h4>Add New Reward</h4>
        <form class="stack" id="newRewardForm">
          <label>Reward Name<input name="name" required /></label>
          <label>Description<textarea name="description"></textarea></label>
          <label>Cost<input name="cost" type="number" min="1" value="100" required /></label>
          <label>Stock<input name="stock" type="number" min="0" value="1" required /></label>
          <label>Source<select name="source"><option value="coop">coop</option><option value="canteen">canteen</option></select></label>
          <button type="submit">Add Reward</button>
          ${message("", "")}
        </form>
      </article>
    </div>`;
  }
  if (state.adminTab === "stock-approvals") {
    return `<article class="card">
      <h4>Manage Redemptions</h4>
      <div class="inline-actions">
        <select id="adminStatus">${["pending", "approved", "rejected", "insufficient"].map((status) => `<option value="${status}" ${status === state.adminRedemptionStatus ? "selected" : ""}>${status}</option>`).join("")}</select>
      </div>
      ${data.redemptions.length ? `<table class="table"><thead><tr><th>Student</th><th>Class</th><th>Pts</th><th>Reward</th><th>Cost</th><th>Stock</th><th>Status</th><th>Date</th><th>Decision</th></tr></thead><tbody>${data.redemptions.map((row) => `<tr>
        <td>${escapeHtml(row.student_name)}</td><td>${escapeHtml(row.class_name)}</td><td>${row.points}</td><td>${escapeHtml(row.reward_name)}</td><td>${row.cost}</td><td>${row.stock}</td><td>${escapeHtml(row.status)}</td><td>${escapeHtml(new Date(row.date).toLocaleString())}</td><td><select data-redemption-decision="${row.id}"><option value="">-</option><option value="Approve">Approve</option><option value="Reject">Reject</option></select></td>
      </tr>`).join("")}</tbody></table><button id="applyRedemptionDecisions">Apply Decisions</button>` : `<p class="meta">No ${escapeHtml(state.adminRedemptionStatus)} requests.</p>`}
    </article>`;
  }
  if (state.adminTab === "point-transactions") {
    return `<article class="card">
      <h4>Point Transactions</h4>
      ${data.point_transactions.length ? `<table class="table"><thead><tr><th>Student</th><th>Class</th><th>Teacher</th><th>Category</th><th>Reason</th><th>Points</th><th>Date</th></tr></thead><tbody>${data.point_transactions.map((row) => `<tr>
        <td>${escapeHtml(row.student_name)}</td><td>${escapeHtml(row.class_name)}</td><td>${escapeHtml(row.teacher_name)}</td><td>${escapeHtml(row.category)}</td><td>${escapeHtml(row.reason)}</td><td>${row.points}</td><td>${escapeHtml(new Date(row.date).toLocaleString())}</td>
      </tr>`).join("")}</tbody></table>` : `<p class="meta">No point transactions found for this class.</p>`}
    </article>`;
  }
  if (state.adminTab === "redemption-insights") {
    return `<div class="card-grid">
      <article class="card"><h4>Status Counts</h4>${renderBars(data.redemption_insights.status_counts, "status", "count")}<p class="meta">Total Points Spent: ${data.redemption_insights.total_spent}</p></article>
      <article class="card"><h4>Approved Redemptions Over Time</h4>${renderLine(data.redemption_insights.timeline, "count")}</article>
      <article class="card"><h4>Top Rewards</h4>${renderBars(data.redemption_insights.top_rewards, "name", "count")}</article>
      <article class="card"><h4>Top Students</h4>${renderBars(data.redemption_insights.top_students, "name", "spent")}</article>
    </div>`;
  }
  return `<article class="card">
    <h4>Reset User Password</h4>
    <form class="stack" id="resetPasswordForm">
      <label>Username<input name="username" required /></label>
      <button type="submit">Reset to password123</button>
      ${message("", "")}
    </form>
  </article>`;
}

async function renderAdminArea() {
  const data = await api(`/api/admin/dashboard?class_name=${encodeURIComponent(state.adminClass || state.teacherClass || "")}&redemption_status=${encodeURIComponent(state.adminRedemptionStatus)}`);
  if (!state.adminClass) state.adminClass = data.selected_class;
  const adminArea = document.getElementById("adminArea");
  adminArea.innerHTML = `
    <section class="panel page-card" style="margin-top:16px;">
      <div class="dashboard-top">
        <h3>Admin Dashboard</h3>
        <select id="adminClass">${data.classes.map((className) => `<option value="${escapeHtml(className)}" ${className === data.selected_class ? "selected" : ""}>${escapeHtml(className)}</option>`).join("")}</select>
      </div>
      ${renderTabs(adminTabs(), state.adminTab, "admin")}
      ${renderAdminContent(data)}
    </section>
  `;
  bindTabs("admin", (value) => {
    state.adminTab = value;
  });
  document.getElementById("adminClass")?.addEventListener("change", async (event) => {
    state.adminClass = event.target.value;
    await renderAdminArea();
  });
  document.querySelectorAll("[data-assign-teacher]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api("/api/admin/teacher-assignment", {
        method: "POST",
        body: JSON.stringify({
          teacher_id: Number(button.dataset.assignTeacher),
          class_name: state.adminClass,
          assign: button.dataset.assignState === "on",
        }),
      });
      await renderAdminArea();
    });
  });
  document.getElementById("newRewardForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    try {
      await api("/api/admin/rewards", {
        method: "POST",
        body: JSON.stringify({
          name: formData.get("name"),
          description: formData.get("description"),
          cost: Number(formData.get("cost")),
          stock: Number(formData.get("stock")),
          source: formData.get("source"),
        }),
      });
      await renderAdminArea();
    } catch (error) {
      event.target.querySelector(".message").outerHTML = message(error.message, "error");
    }
  });
  document.querySelectorAll(".reward-edit").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      await api(`/api/admin/rewards/${form.dataset.rewardId}`, {
        method: "PATCH",
        body: JSON.stringify({
          cost: Number(formData.get("cost")),
          stock: Number(formData.get("stock")),
        }),
      });
      await renderAdminArea();
    });
  });
  document.querySelectorAll("[data-delete-reward]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/admin/rewards/${button.dataset.deleteReward}`, { method: "DELETE" });
      await renderAdminArea();
    });
  });
  document.getElementById("adminStatus")?.addEventListener("change", async (event) => {
    state.adminRedemptionStatus = event.target.value;
    await renderAdminArea();
  });
  document.getElementById("applyRedemptionDecisions")?.addEventListener("click", async () => {
    const items = Array.from(document.querySelectorAll("[data-redemption-decision]"))
      .map((select) => ({ id: Number(select.dataset.redemptionDecision), decision: select.value }))
      .filter((item) => item.decision);
    if (!items.length) return;
    await api("/api/admin/redemptions/decide", { method: "POST", body: JSON.stringify({ items }) });
    await renderAdminArea();
  });
  document.getElementById("resetPasswordForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    try {
      await api("/api/admin/reset-password", {
        method: "POST",
        body: JSON.stringify({ username: formData.get("username") }),
      });
      event.target.querySelector(".message").outerHTML = message("Password reset to password123.", "success");
    } catch (error) {
      event.target.querySelector(".message").outerHTML = message(error.message, "error");
    }
  });
}

function getQueryMode() {
  const params = new URLSearchParams(window.location.search);
  const action = params.get("action");
  const sid = params.get("sid");
  return action && sid ? { action, sid } : null;
}

async function renderQrMode() {
  const query = getQueryMode();
  if (!query) return false;

  if (query.action === "redeem") {
    const data = await api(`/api/students/${query.sid}/dashboard`);
    appRoot.innerHTML = `
      <div class="stack">
        <h3>Student Reward Redemption</h3>
        <p class="meta">${escapeHtml(data.student.name)} - ${data.student.total_points} pts</p>
        <div class="list">${data.rewards.length ? data.rewards.map((reward) => `<div class="list-item">
          <div class="row"><strong>${escapeHtml(reward.name)}</strong><span class="pill">${reward.cost} pts</span></div>
          <p class="meta">Stock: ${reward.stock}</p>
          <button data-qr-redeem="${reward.id}">Request Redemption</button>
        </div>`).join("") : `<p class="meta">No rewards available right now.</p>`}</div>
        <button id="backHome">Back to Main App</button>
        ${message("", "")}
      </div>
    `;
    document.getElementById("backHome").addEventListener("click", () => {
      window.location.search = "";
    });
    document.querySelectorAll("[data-qr-redeem]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await api("/api/redemptions/request", {
            method: "POST",
            body: JSON.stringify({ student_id: Number(query.sid), reward_id: Number(button.dataset.qrRedeem) }),
          });
          appRoot.querySelector(".message").outerHTML = message("Request submitted. An admin will review it shortly.", "success");
        } catch (error) {
          appRoot.querySelector(".message").outerHTML = message(error.message, "error");
        }
      });
    });
    return true;
  }

  if (query.action === "addpoints") {
    const data = await api(`/api/students/${query.sid}/dashboard`);
    appRoot.innerHTML = `
      <div class="stack">
        <h3>Add Points to Student</h3>
        <p class="meta">Student: ${escapeHtml(data.student.name)} (Class: ${escapeHtml(data.student.class_name)})</p>
        <form class="stack" id="qrTeacherLogin">
          <label>Teacher Username<input name="username" required /></label>
          <label>Password<input type="password" name="password" required /></label>
          <label>Category<select name="category">${deedCategories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("")}</select></label>
          <label>Reason<input name="reason" required /></label>
          <label>Points<input type="number" min="1" max="100" name="points" value="10" required /></label>
          <button type="submit">Add Deed</button>
          <button type="button" id="backHome">Back to Main App</button>
          ${message("", "")}
        </form>
      </div>
    `;
    document.getElementById("backHome").addEventListener("click", () => {
      window.location.search = "";
    });
    document.getElementById("qrTeacherLogin").addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(event.target);
      try {
        const teacher = await api("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({
            username: formData.get("username"),
            password: formData.get("password"),
          }),
        });
        if (!["teacher", "admin"].includes(teacher.role)) throw new Error("Please login as teacher to proceed.");
        await api(`/api/teachers/${teacher.teacher_id}/activities`, {
          method: "POST",
          body: JSON.stringify({
            student_id: Number(query.sid),
            category: formData.get("category"),
            reason: formData.get("reason"),
            points: Number(formData.get("points")),
          }),
        });
        event.target.querySelector(".message").outerHTML = message("Points added successfully.", "success");
      } catch (error) {
        event.target.querySelector(".message").outerHTML = message(error.message, "error");
      }
    });
    return true;
  }
  return false;
}

async function render() {
  if (await renderQrMode()) return;
  if (state.user) {
    if (state.user.role === "student") return renderStudentDashboard();
    return renderTeacherDashboard();
  }
  if (state.page === "welcome") return renderWelcome();
  if (state.page === "select_role_login") return renderRoleSelection("login");
  if (state.page === "select_role_signup") return renderRoleSelection("signup");
  if (state.page === "login_student") return renderLogin("student");
  if (state.page === "login_teacher") return renderLogin("teacher");
  if (state.page === "signup") return renderSignup();
  renderWelcome();
}

window.addEventListener("load", async () => {
  try {
    await loadClasses();
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js");
    await render();
  } catch (error) {
    appRoot.innerHTML = `
      <div class="stack">
        <h3>App Loading Error</h3>
        <p class="meta">The app shell loaded, but startup data failed.</p>
        <p class="message error">${escapeHtml(error.message || "Unknown error")}</p>
        <button id="retryLoad">Retry</button>
        <button id="showWelcome">Show Login Page</button>
      </div>
    `;
    document.getElementById("retryLoad")?.addEventListener("click", async () => {
      await render();
    });
    document.getElementById("showWelcome")?.addEventListener("click", () => {
      state.user = null;
      state.page = "welcome";
      renderWelcome();
    });
  }
});
