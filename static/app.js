
document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("pdfFiles");
  const dropzone = document.getElementById("dropzone");
  const chooseButton = document.getElementById("chooseFiles");
  const fileList = document.getElementById("fileList");
  const fileStatus = document.getElementById("fileStatus");
  const uploadForm = document.getElementById("uploadForm");
  const uploadButton = document.getElementById("uploadButton");
  const searchForm = document.getElementById("searchForm");
  const searchButton = document.getElementById("searchButton");
  const questionInput = document.getElementById("question");

  // Open the native file picker.
  chooseButton.addEventListener("click", (event) => {
    event.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    fileInput.click();
  });

  dropzone.addEventListener("keydown", (event) => {
    if (event.target !== dropzone) return;

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });

  // File drag and drop.
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer.files);
    const validFiles = files.filter((file) =>
      file.name.toLowerCase().endsWith(".pdf")
    );

    if (validFiles.length !== files.length) {
      fileStatus.textContent =
        "PDF olmayan dosyalar seçime dahil edilmedi.";
    } else {
      fileStatus.textContent = "";
    }

    const transfer = new DataTransfer();

    validFiles.forEach((file) => transfer.items.add(file));
    fileInput.files = transfer.files;

    renderFiles();
  });

  fileInput.addEventListener("change", () => {
    fileStatus.textContent = "";
    renderFiles();
  });

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function renderFiles() {
    const files = Array.from(fileInput.files);

    fileList.replaceChildren();

    files.forEach((file) => {
      const chip = document.createElement("div");
      chip.className = "file-chip";

      const icon = document.createElement("span");
      icon.textContent = "▤";

      const name = document.createElement("span");
      name.className = "file-chip-name";
      name.textContent = file.name;

      const size = document.createElement("span");
      size.className = "file-chip-size";
      size.textContent = formatSize(file.size);

      chip.append(icon, name, size);
      fileList.appendChild(chip);
    });
  }

  // Prevent duplicate uploads.
  uploadForm.addEventListener("submit", (event) => {
    const files = Array.from(fileInput.files);

    if (files.length === 0) {
      event.preventDefault();
      fileStatus.textContent = "Lütfen bir PDF seç.";
      return;
    }

    if (files.some((file) => !file.name.toLowerCase().endsWith(".pdf"))) {
      event.preventDefault();
      fileStatus.textContent = "Yalnızca PDF dosyaları yüklenebilir.";
      return;
    }

    uploadButton.disabled = true;
    uploadButton.textContent = "PDF'ler işleniyor...";
  });

  // Example question shortcuts.
  document.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.question;
      questionInput.focus();
    });
  });

  // Show search loading state.
  searchForm.addEventListener("submit", (event) => {
    if (!questionInput.value.trim()) {
      event.preventDefault();
      questionInput.focus();
      return;
    }

    searchButton.disabled = true;
    searchButton.textContent = "Aranıyor...";
  });

  // Bring search results into view after a completed search.
  if (document.body.dataset.hasResults === "true") {
    const results = document.getElementById("results");

    if (results) {
      results.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }
  }
});
