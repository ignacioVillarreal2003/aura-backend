(function () {
  function toggleGroupsSection() {
    var roleInputs = document.querySelectorAll('input[name="roles"]');
    var groupsSection = document.querySelector('.groups-section');
    if (!groupsSection || roleInputs.length === 0) {
      return;
    }

    var selected = null;
    roleInputs.forEach(function (input) {
      if (input.checked) {
        selected = input;
      }
    });

    var isAdmin = selected && selected.value === selected.getAttribute('data-admin-role');
    if (isAdmin) {
      groupsSection.style.display = 'none';
    } else {
      groupsSection.style.display = '';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var body = document.body;
    if (!body || !body.classList.contains('add-form')) {
      return;
    }

    var roleInputs = document.querySelectorAll('input[name="roles"]');
    roleInputs.forEach(function (input) {
      var label = input.nextElementSibling;
      if (label && label.textContent.trim() === 'Administrador') {
        input.setAttribute('data-admin-role', input.value);
      }
      input.addEventListener('change', toggleGroupsSection);
    });

    toggleGroupsSection();
  });
})();
