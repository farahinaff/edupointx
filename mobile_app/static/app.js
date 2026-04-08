const authPanel = document.getElementById("authPanel");
const dashboard = document.getElementById("dashboard");
const authMessage = document.getElementById("authMessage");
const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const classSelect = document.getElementById("classSelect");
const signupRole = document.getElementById("signupRole");
const classField = document.getElementById("classField");

const state = {
  user: JSON.parse(localStorage.getItem("edupointx-user") || "null"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Something went wrong.");
  }
  return data;
}

function showMessage(text, isError = false) {
  authMessage.textContent = text;
  authMessage.style.color = isError ? "#b91c1c" : "#0f766e";
}

function setUser(user) {
  state.user = user;
  localStorage.setItem("edupointx-user", JSON.stringify(user));
  render();
}

function logout() {
  state.user = null;
  localStorage.removeItem("edupointx-user");
  render();
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  loginForm.classList.toggle("hidden", name !== "login");
  signupForm.classList.toggle("hidden", name !== "signup");
  showMessage("");
}

async function loadClasses() {
  const classes = await api("/api/classes");
  classSelect.innerHTML = classes.map((item) => `<option value="${item}">${item}</option>`).join("");
}

function renderStudent(data) {
  const rewardItems = data.rewards
    .map(
      (reward) => `
        <article class="list-item">
          <div class="row"><strong>${reward.name}</strong><span class="pill">${reward.cost} pts</span></div>
          <p class="meta">${reward.description}</p>
          <p class="meta">Stock: ${reward.stock} · Source: ${reward.source}</p>
        </article>`
    )
    .join("");

  const activityItems = data.activities
    .map(
      (activity) => `
        <article class="list-item">
          <div class="row"><strong>${activity.category}</strong><span>${activity.points} pts</span></div>
          <p class="meta">${activity.reason}</p>
          <p class="meta">${new Date(activity.created_at).toLocaleString()}</p>
        </article>`
    )
    .join("");

  const leaderboardItems = data.leaderboard
    .map(
      (item, index) => `
        <article class="list-item row">
          <span>${index + 1}. ${item.name}</span>
          <strong>${item.points} pts</strong>
        </article>`
    )
    .join("");

  dashboard.innerHTML = `
    <div class="dashboard-head">
      <div>
        <p class="eyebrow">Student Dashboard</p>
        <h2>${data.name}</h2>
        <p class="meta">${data.class_name}</p>
      </div>
      <button class="secondary" id="logoutButton">Logout</button>
    </div>
    <section class="grid two">
      <article class="card">
        <p class="meta">Available points</p>
        <div class="metric">${data.total_points}</div>
      </article>
      <article class="card">
        <h3>Top in class</h3>
        <div class="list">${leaderboardItems}</div>
      </article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>Rewards</h3>
        <div class="list">${rewardItems}</div>
      </article>
      <article class="card">
        <h3>Activity History</h3>
        <div class="list">${activityItems || "<p class='meta'>No activity yet.</p>"}</div>
      </article>
    </section>
  `;
  document.getElementById("logoutButton").addEventListener("click", logout);
}

function renderTeacher(data, classes) {
  const studentOptions = data.students
    .map((student) => `<option value="${student.id}">${student.name}</option>`)
    .join("");
  const classOptions = classes
    .map((item) => `<option value="${item}" ${item === data.class_name ? "selected" : ""}>${item}</option>`)
    .join("");
  const studentItems = data.students
    .map((student) => `<article class="list-item row"><span>${student.name}</span><strong>${student.points} pts</strong></article>`)
    .join("");
  const categoryItems = data.category_breakdown
    .map((item) => `<article class="list-item row"><span>${item.category}</span><strong>${item.count}</strong></article>`)
    .join("");
  const recentItems = data.recent_activities
    .map(
      (item) => `
        <article class="list-item">
          <div class="row"><strong>${item.student_name}</strong><span>${item.points} pts</span></div>
          <p class="meta">${item.category} · ${item.reason}</p>
        </article>`
    )
    .join("");

  dashboard.innerHTML = `
    <div class="dashboard-head">
      <div>
        <p class="eyebrow">${state.user.role === "admin" ? "Admin View" : "Teacher Dashboard"}</p>
        <h2>${state.user.display_name}</h2>
      </div>
      <button class="secondary" id="logoutButton">Logout</button>
    </div>
    <section class="grid two">
      <article class="card stack">
        <h3>Selected Class</h3>
        <label>
          Class
          <select id="teacherClassSelect">${classOptions}</select>
        </label>
        <form id="activityForm" class="stack">
          <label>Student<select name="student_id">${studentOptions}</select></label>
          <label>Category
            <select name="category">
              <option value="Discipline">Discipline</option>
              <option value="Academic">Academic</option>
              <option value="Leadership">Leadership</option>
              <option value="Sports">Sports</option>
              <option value="Volunteerism">Volunteerism</option>
            </select>
          </label>
          <label>Reason<input type="text" name="reason" required /></label>
          <label>Points<input type="number" name="points" min="1" max="100" value="10" required /></label>
          <button type="submit" class="primary">Add Activity</button>
        </form>
      </article>
      <article class="card">
        <h3>Students</h3>
        <div class="list">${studentItems}</div>
      </article>
    </section>
    <section class="grid two">
      <article class="card">
        <h3>Category Breakdown</h3>
        <div class="list">${categoryItems || "<p class='meta'>No categories yet.</p>"}</div>
      </article>
      <article class="card">
        <h3>Recent Activity</h3>
        <div class="list">${recentItems || "<p class='meta'>No activity yet.</p>"}</div>
      </article>
    </section>
  `;

  document.getElementById("logoutButton").addEventListener("click", logout);
  document.getElementById("teacherClassSelect").addEventListener("change", async (event) => {
    await loadTeacherDashboard(event.target.value);
  });
  document.getElementById("activityForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    try {
      await api(`/api/teachers/${state.user.teacher_id}/activities`, {
        method: "POST",
        body: JSON.stringify({
          student_id: Number(formData.get("student_id")),
          category: formData.get("category"),
          reason: formData.get("reason"),
          points: Number(formData.get("points")),
        }),
      });
      await loadTeacherDashboard(document.getElementById("teacherClassSelect").value);
    } catch (error) {
      alert(error.message);
    }
  });
}

function renderAdmin(overview) {
  const classCards = overview.class_totals
    .map(
      (item) => `<article class="list-item"><strong>${item.class_name}</strong><p class="meta">${item.student_count} students · ${item.total_points} pts</p></article>`
    )
    .join("");
  const rewardCards = overview.rewards
    .map(
      (reward) => `<article class="list-item"><strong>${reward.name}</strong><p class="meta">${reward.cost} pts · ${reward.stock} left</p></article>`
    )
    .join("");
  const teacherCards = overview.teacher_assignments
    .map(
      (item) => `<article class="list-item row"><span>${item.teacher_name}</span><span>${item.class_name}</span></article>`
    )
    .join("");

  return `
    <section class="grid two">
      <article class="card"><h3>Class Totals</h3><div class="list">${classCards}</div></article>
      <article class="card"><h3>Rewards</h3><div class="list">${rewardCards}</div></article>
    </section>
    <section class="grid">
      <article class="card"><h3>Teacher Assignments</h3><div class="list">${teacherCards}</div></article>
    </section>
  `;
}

async function loadTeacherDashboard(initialClass) {
  const classes = await api(`/api/teachers/${state.user.teacher_id}/classes`);
  if (!classes.length) {
    dashboard.innerHTML = `
      <div class="dashboard-head">
        <div>
          <p class="eyebrow">Teacher Dashboard</p>
          <h2>${state.user.display_name}</h2>
          <p class="meta">No classes assigned yet.</p>
        </div>
        <button class="secondary" id="logoutButton">Logout</button>
      </div>
      <article class="card">
        <p class="meta">Ask an admin to assign a class before adding activities.</p>
      </article>
    `;
    document.getElementById("logoutButton").addEventListener("click", logout);
    return;
  }
  const selectedClass = initialClass || classes[0];
  const data = await api(
    `/api/teachers/${state.user.teacher_id}/dashboard?class_name=${encodeURIComponent(selectedClass)}`
  );
  renderTeacher(data, classes);

  if (state.user.role === "admin") {
    const overview = await api("/api/admin/overview");
    dashboard.insertAdjacentHTML("beforeend", renderAdmin(overview));
  }
}

async function render() {
  if (!state.user) {
    authPanel.classList.remove("hidden");
    dashboard.classList.add("hidden");
    dashboard.innerHTML = "";
    return;
  }

  authPanel.classList.add("hidden");
  dashboard.classList.remove("hidden");

  if (state.user.role === "student") {
    const data = await api(`/api/students/${state.user.student_id}/dashboard`);
    renderStudent(data);
    return;
  }

  await loadTeacherDashboard();
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

signupRole.addEventListener("change", () => {
  classField.classList.toggle("hidden", signupRole.value !== "student");
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(loginForm);
  try {
    const user = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: formData.get("username"),
        password: formData.get("password"),
      }),
    });
    setUser(user);
  } catch (error) {
    showMessage(error.message, true);
  }
});

signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(signupForm);
  try {
    const user = await api("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        full_name: formData.get("full_name"),
        username: formData.get("username"),
        password: formData.get("password"),
        role: formData.get("role"),
        class_name: formData.get("role") === "student" ? formData.get("class_name") : null,
      }),
    });
    setUser(user);
  } catch (error) {
    showMessage(error.message, true);
  }
});

window.addEventListener("load", async () => {
  await loadClasses();
  classField.classList.toggle("hidden", signupRole.value !== "student");
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js");
  }
  await render();
});
