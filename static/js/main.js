function toggleFiltros(){document.getElementById("sidebar-filtros")?.classList.toggle("ativo");}
function confirmarRemocao(msg){return confirm(msg||"Tens a certeza?");}
document.addEventListener("DOMContentLoaded",()=>{
  const inputCV=document.querySelector("#cv");
  if(inputCV){inputCV.addEventListener("change",function(){
    const p=document.createElement("p"); p.textContent="📎 "+(this.files[0]?.name||"");
    this.parentNode.appendChild(p);
  });}
});
function toggleMenu(){
  const nav = document.getElementById("nav-menu");
  nav.classList.toggle("ativo");
}

function toggleMenu(){
  const nav=document.getElementById("nav-menu");
  nav.classList.toggle("ativo");
}

function toggleDarkMode(){
  document.body.classList.toggle("dark");
  document.body.classList.toggle("light");
}
