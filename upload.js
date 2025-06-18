document.addEventListener("DOMContentLoaded", function () {
  const container = document.getElementById("inputContainer");

  for (let i = 1; i <= 13; i++) {
    const label = document.createElement("label");
    label.textContent = `Input Bagian ${i}`;
    label.setAttribute("for", `bagian${i}`);

    const input = document.createElement("input");
    input.type = "number";
    input.id = `bagian${i}`;
    input.name = `bagian${i}`;
    input.required = true;
    input.className = "form-control";

    const div = document.createElement("div");
    div.className = "mb-3";
    div.appendChild(label);
    div.appendChild(input);

    container.appendChild(div);
  }
});
