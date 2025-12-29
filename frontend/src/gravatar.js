import md5 from "blueimp-md5";

export function getGravatarUrl(email, size = 64) {
  const hash = md5(email.trim().toLowerCase());
  return `https://www.gravatar.com/avatar/${hash}?s=${size}&d=404`;
}

export function setupUserAvatar(email, avatarElement, initialElement) {
  if (!avatarElement || !initialElement) return;

  const initial = email.charAt(0).toUpperCase();
  initialElement.textContent = initial;

  const gravatarUrl = getGravatarUrl(email, 64);
  const img = new Image();

  img.onload = () => {
    initialElement.style.display = "none";
    const imgEl = document.createElement("img");
    imgEl.src = gravatarUrl;
    imgEl.alt = initial;
    avatarElement.appendChild(imgEl);
  };

  img.onerror = () => {
    initialElement.textContent = initial;
  };

  img.src = gravatarUrl;
}
