# DIU — Droguería Industrial Uruguaya
## Aplicación Web Flask + Panel Admin

---

## Instalación local (desarrollo)

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/diu-app.git
cd diu-app
```

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
# Editá .env con tus valores reales
```

Contenido mínimo del `.env`:
```
SECRET_KEY=una-clave-larga-y-aleatoria
ADMIN_EMAIL=tu-email@dominio.com
ADMIN_PASSWORD=tu-contrasena-segura
ADMIN_NAME=Tu Nombre
```

### 5. Correr la aplicación
```bash
python app.py
```

Abrí http://localhost:5000

---

## Subir a GitHub

```bash
git init
git add .
git commit -m "Initial commit — DIU app"
git remote add origin https://github.com/tu-usuario/diu-app.git
git branch -M main
git push -u origin main
```

> El `.gitignore` ya excluye `.env`, la base de datos y las imágenes subidas.

---

## Deploy en producción

### Opción A — Railway (recomendado)
1. https://railway.app → New Project → Deploy from GitHub repo
2. Seleccioná el repositorio
3. En Variables, agregá: `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`
4. Railway detecta el `Procfile` automáticamente

### Opción B — Render
1. https://render.com → New Web Service → GitHub repo
2. Build: `pip install -r requirements.txt`
3. Start: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. Agregá las variables de entorno

### Opción C — VPS propio (Ubuntu)
```bash
git clone https://github.com/tu-usuario/diu-app.git && cd diu-app
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --daemon
```

---

## Seguridad

- `.env` NUNCA se sube a git (está en `.gitignore`)
- `SECRET_KEY` debe ser una cadena larga y aleatoria en producción
- La base de datos (`instance/diu.db`) tampoco se sube a git
- Cambiá la contraseña del admin después del primer login desde Admin → Usuarios

---

## Panel Admin

URL: `/admin`

| Sección | Funcionalidades |
|---------|----------------|
| Dashboard | Estadísticas, pedidos y contactos recientes |
| Productos | CRUD completo · imagen · precio · stock · destacado |
| Categorías | CRUD · color · ícono · orden |
| Usuarios | CRUD · roles: admin / staff / customer |
| Pedidos | Lista, detalle, cambio de estado |
| Novedades | CRUD · publicar / despublicar |
| Contactos | Bandeja de mensajes entrantes |
| Configuración | Teléfono, email, dirección, redes sociales |

---

Desarrollado para DIU — Droguería Industrial Uruguaya · 2026
