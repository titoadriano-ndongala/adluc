// Confirmação ao apagar vagas/candidaturas
function confirmarRemocao(msg) {
    return confirm(msg || "Tens a certeza que queres remover?");
}

// Mostrar nome do ficheiro ao selecionar CV
document.addEventListener("DOMContentLoaded", () => {
    const inputCV = document.querySelector("#cv");
    if (inputCV) {
        inputCV.addEventListener("change", function () {
            const label = document.createElement("p");
            label.textContent = "📎 Selecionado: " + this.files[0].name;
            this.parentNode.appendChild(label);
        });
    }
});

// Abrir/fechar filtros no mobile
function toggleFiltros() {
    const sidebar = document.getElementById("sidebar-filtros");
    sidebar.classList.toggle("ativo");
}

