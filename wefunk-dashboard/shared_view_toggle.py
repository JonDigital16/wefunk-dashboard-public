TOGGLE_JS = r"""
<script>
function setCardTableView(gridId, tableId, toggleClass, storageKey, view){
    const grid=document.getElementById(gridId);
    const table=document.getElementById(tableId);
    const buttons=document.querySelectorAll("." + toggleClass + " button");

    if(view==="table"){
        if(grid) grid.style.display="none";
        if(table) table.style.display="table";
        if(buttons.length>1){
            buttons[0].classList.remove("active");
            buttons[1].classList.add("active");
        }
    }else{
        if(grid) grid.style.display="grid";
        if(table) table.style.display="none";
        if(buttons.length>1){
            buttons[0].classList.add("active");
            buttons[1].classList.remove("active");
        }
        view="cards";
    }

    localStorage.setItem(storageKey,view);
}

function initCardTableView(gridId, tableId, toggleClass, storageKey){
    setCardTableView(
        gridId,
        tableId,
        toggleClass,
        storageKey,
        localStorage.getItem(storageKey) || "cards"
    );
}
</script>
"""
