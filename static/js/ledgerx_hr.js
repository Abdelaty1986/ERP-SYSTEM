// LedgerX HR Enterprise helpers
(function(){
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('input[type="date"]').forEach(function(el){
      if(!el.value && el.name === 'work_date') el.value = new Date().toISOString().slice(0,10);
    });
  });
})();
