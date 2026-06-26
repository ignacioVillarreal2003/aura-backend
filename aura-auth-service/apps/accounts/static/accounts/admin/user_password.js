(function () {
  function generatePassword(length) {
    var chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
    var result = '';
    for (var i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var input = document.querySelector('#id_password') || document.querySelector('input[name="password"]');
    var chosenTitle = document.querySelector('.selector-chosen h2');
    if (chosenTitle && chosenTitle.textContent) {
      chosenTitle.textContent = chosenTitle.textContent.replace('Grupos elegidos', 'Grupos Elegidos');
    }

    if (!input) {
      return;
    }

    var container = input.closest('.form-row') || input.parentElement;
    if (!container) {
      return;
    }

    var button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Generar';
    button.style.marginLeft = '8px';
    button.className = 'button';

    button.addEventListener('click', function () {
      input.value = generatePassword(12);
    });

    input.insertAdjacentElement('afterend', button);
  });
})();
