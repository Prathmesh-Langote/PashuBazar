
const API_BASE = "https://pashubazar.onrender.com";

const loginSection = document.getElementById("loginSection");
const dashboardSection = document.getElementById("dashboardSection");
const loginForm = document.getElementById("adminLoginForm");
const loginMessage = document.getElementById("loginMessage");
const dashboardMessage = document.getElementById("dashboardMessage");
const animalList = document.getElementById("animalList");

let allAnimals = [];

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: "include"
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.message || `Request failed: ${response.status}`);
    }

    return data;
}

function showLogin() {
    loginSection.hidden = false;
    dashboardSection.hidden = true;
}

function showDashboard() {
    loginSection.hidden = true;
    dashboardSection.hidden = false;
}

async function checkAdminSession() {
    try {
        await apiRequest("/api/admin/check");
        showDashboard();
        await loadAnimals();
    } catch (error) {
        showLogin();
    }
}

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    loginMessage.textContent = "Logging in...";

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
        await apiRequest("/api/admin/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        loginForm.reset();
        loginMessage.textContent = "";
        showDashboard();
        await loadAnimals();
    } catch (error) {
        loginMessage.textContent = error.message;
    }
});

function updateStatistics(animals) {
    document.getElementById("totalListings").textContent = animals.length;

    const categories = new Set(
        animals.map(a => (a.category || "").trim()).filter(Boolean)
    );

    document.getElementById("totalCategories").textContent =
        categories.size;

    const categoryFilter = document.getElementById("categoryFilter");
    const selectedCategory = categoryFilter.value;

    categoryFilter.replaceChildren();

    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All Categories";
    categoryFilter.appendChild(allOption);

    [...categories].sort().forEach(category => {
        const option = document.createElement("option");
        option.value = category;
        option.textContent = category;
        categoryFilter.appendChild(option);
    });

    if (categories.has(selectedCategory)) {
        categoryFilter.value = selectedCategory;
    }
}

function createTextElement(tag, text) {
    const element = document.createElement(tag);
    element.textContent = text;
    return element;
}

function renderAnimals() {
    const search = document.getElementById("searchInput").value
        .trim().toLowerCase();
    const category = document.getElementById("categoryFilter").value;
    const breed = document.getElementById("breedFilter").value
        .trim().toLowerCase();
    const location = document.getElementById("locationFilter").value
        .trim().toLowerCase();

    const filtered = allAnimals.filter(animal => {
        const animalBreed = (animal.breed || "").toLowerCase();
        const animalLocation = (animal.location || "").toLowerCase();
        const animalCategory = animal.category || "";

        const matchesSearch =
            !search ||
            animalBreed.includes(search) ||
            animalLocation.includes(search) ||
            animalCategory.toLowerCase().includes(search);

        return matchesSearch &&
            (!category || animalCategory === category) &&
            (!breed || animalBreed.includes(breed)) &&
            (!location || animalLocation.includes(location));
    });

    animalList.replaceChildren();

    if (filtered.length === 0) {
        animalList.appendChild(
            createTextElement("p", "No matching animal listings found.")
        );
        return;
    }

    filtered.forEach(animal => {
        const card = document.createElement("article");
        card.className = "animal-card";

        if (animal.photo) {
            const img = document.createElement("img");
            img.src = animal.photo || "";
            img.alt = animal.category || "Animal photo";
            img.onerror = () => img.remove();
            card.appendChild(img);
        }

        card.appendChild(createTextElement(
            "h3",
            `${animal.category || "Animal"} - ${animal.breed || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Age: ${animal.age || "N/A"} | Gender: ${animal.gender || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Price: ₹${animal.price ?? "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Location: ${animal.location || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Health: ${animal.health || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Vaccination: ${animal.vaccination || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Description: ${animal.description || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Seller: ${animal.sellerName || "N/A"}`
        ));

        card.appendChild(createTextElement(
            "p",
            `Mobile: ${animal.sellerMobile || "Not available"}`
        ));

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "delete-button";
        deleteButton.textContent = "Delete Listing";

        deleteButton.addEventListener("click", async function () {
            const confirmed = confirm(
                `Delete ${animal.category || "this"} - ${animal.breed || "animal"} listing permanently?`
            );

            if (!confirmed) return;

            deleteButton.disabled = true;
            deleteButton.textContent = "Deleting...";

            try {
                await apiRequest(
                    `/api/admin/animals/${encodeURIComponent(animal._id)}`,
                    { method: "DELETE" }
                );

                allAnimals = allAnimals.filter(
                    item => item._id !== animal._id
                );

                updateStatistics(allAnimals);
                renderAnimals();

                dashboardMessage.textContent =
                    "Animal listing deleted successfully.";
            } catch (error) {
                dashboardMessage.textContent = error.message;
                deleteButton.disabled = false;
                deleteButton.textContent = "Delete Listing";
            }
        });

        card.appendChild(deleteButton);
        animalList.appendChild(card);
    });
}

async function loadAnimals() {
    dashboardMessage.textContent = "Loading listings...";

    try {
        const data = await apiRequest("/api/admin/animals");

        if (data.status !== "success" || !Array.isArray(data.animals)) {
            throw new Error("Unexpected response from backend.");
        }

        allAnimals = data.animals;
        updateStatistics(allAnimals);
        renderAnimals();

        dashboardMessage.textContent =
            `Showing ${allAnimals.length} total listings.`;
    } catch (error) {
        dashboardMessage.textContent =
            `Could not load listings: ${error.message}`;
    }
}

["searchInput", "categoryFilter", "breedFilter", "locationFilter"]
    .forEach(id => {
        document.getElementById(id).addEventListener("input", renderAnimals);
        document.getElementById(id).addEventListener("change", renderAnimals);
    });

document.getElementById("clearFilters").addEventListener("click", () => {
    document.getElementById("searchInput").value = "";
    document.getElementById("categoryFilter").value = "";
    document.getElementById("breedFilter").value = "";
    document.getElementById("locationFilter").value = "";
    renderAnimals();
});

document.getElementById("logoutButton").addEventListener("click", async () => {
    try {
        await apiRequest("/api/admin/logout", { method: "POST" });
        allAnimals = [];
        animalList.replaceChildren();
        showLogin();
        dashboardMessage.textContent = "";
        loginMessage.textContent = "Logged out successfully.";
    } catch (error) {
        dashboardMessage.textContent = `Logout failed: ${error.message}`;
    }
});

checkAdminSession();
