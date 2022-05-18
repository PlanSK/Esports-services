function requestConfirmLink(user = '{{ request.user }}') {
    if (confirm('Вы уверены, что хотите направить ссылку?')) {
      let request = new XMLHttpRequest();
      request.open('POST', '{% url "request_confirmation_link" %}', true);
      request.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      request.setRequestHeader('X-CSRFToken', '{{ csrf_token }}');
      request.onreadystatechange = function(){ 
        if ( request.readyState == 4 ) {
          if ( request.status == 200 ) {
            alert("Ссылка для подтверждения направлена");
          } else { 
            alert("Ошибка направления запроса");
          } 
        } 
      }; 
      request.send('user='+ user);
    }
}