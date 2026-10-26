"""BiblioTec - Sistema de biblioteca con interfaz gráfica (Tkinter + SQLite)."""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

DB = "bibliotec.db"
DIAS_PRESTAMO = 7      # días que dura un préstamo
MULTA_POR_DIA = 1.0    # soles por día de retraso


# ---------- Base de datos ----------
def consulta(sql, params=()):
    with sqlite3.connect(DB) as c:
        return c.execute(sql, params).fetchall()


def ejecutar(sql, params=()):
    with sqlite3.connect(DB) as c:
        c.execute(sql, params)


def crear_tablas():
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios(
            usuario TEXT PRIMARY KEY, clave TEXT, rol TEXT);
        CREATE TABLE IF NOT EXISTS lectores(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, dni TEXT UNIQUE, activo INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS libros(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT, autor TEXT, categoria TEXT,
            ejemplares INTEGER, disponibles INTEGER);
        CREATE TABLE IF NOT EXISTS prestamos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_lector INTEGER, id_libro INTEGER,
            fecha_prestamo TEXT, fecha_limite TEXT,
            fecha_devolucion TEXT, multa REAL DEFAULT 0);
        """)
        c.execute("INSERT OR IGNORE INTO usuarios VALUES('admin','1234','bibliotecario')")
        c.execute("INSERT OR IGNORE INTO usuarios VALUES('jefe','1234','jefe')")


# ---------- Utilidades de interfaz ----------
def crear_tabla(padre, columnas, alto=12):
    tabla = ttk.Treeview(padre, columns=columnas, show="headings", height=alto)
    for col in columnas:
        tabla.heading(col, text=col)
        tabla.column(col, width=130)
    tabla.pack(fill="both", expand=True, padx=10, pady=5)
    return tabla


def llenar(tabla, filas):
    tabla.delete(*tabla.get_children())
    for fila in filas:
        tabla.insert("", "end", values=fila)


def campo(padre, texto, col):
    ttk.Label(padre, text=texto).grid(row=0, column=col * 2, padx=5, pady=5)
    entrada = ttk.Entry(padre, width=18)
    entrada.grid(row=0, column=col * 2 + 1, padx=5)
    return entrada


def seleccionado(tabla):
    sel = tabla.selection()
    if not sel:
        messagebox.showinfo("Aviso", "Selecciona una fila de la tabla.")
        return None
    return tabla.item(sel[0])["values"][0]


# ---------- Pestaña: Lectores ----------
class TabLectores(ttk.Frame):
    def __init__(self, padre):
        super().__init__(padre)
        form = ttk.Frame(self)
        form.pack(pady=5)
        self.nombre = campo(form, "Nombre:", 0)
        self.dni = campo(form, "DNI:", 1)
        ttk.Button(form, text="Registrar", command=self.registrar).grid(row=0, column=4, padx=5)
        ttk.Button(form, text="Dar de baja", command=self.baja).grid(row=0, column=5)
        ttk.Button(form, text="Eliminar", command=self.eliminar).grid(row=0, column=6, padx=5)
        self.tabla = crear_tabla(self, ("ID", "Nombre", "DNI", "Estado"))
        self.actualizar()

    def actualizar(self):
        llenar(self.tabla, consulta("SELECT id, nombre, dni, "
                                    "CASE activo WHEN 1 THEN 'Activo' ELSE 'Baja' END "
                                    "FROM lectores"))

    def registrar(self):
        nombre, dni = self.nombre.get().strip(), self.dni.get().strip()
        if not nombre or not dni:
            messagebox.showwarning("Faltan datos", "Nombre y DNI son obligatorios.")
            return
        try:
            ejecutar("INSERT INTO lectores(nombre, dni) VALUES(?,?)", (nombre, dni))
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Ya existe un lector con ese DNI.")
            return
        self.nombre.delete(0, "end")
        self.dni.delete(0, "end")
        self.actualizar()

    def baja(self):
        id_lector = seleccionado(self.tabla)
        if id_lector is not None:
            ejecutar("UPDATE lectores SET activo=0 WHERE id=?", (id_lector,))
            self.actualizar()

    def eliminar(self):
        id_lector = seleccionado(self.tabla)
        if id_lector is None:
            return
        if consulta("SELECT 1 FROM prestamos WHERE id_lector=?", (id_lector,)):
            messagebox.showwarning("No se puede", "El lector tiene préstamos registrados.\n"
                                   "Usa 'Dar de baja' en su lugar.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este lector definitivamente?"):
            ejecutar("DELETE FROM lectores WHERE id=?", (id_lector,))
            self.actualizar()


# ---------- Pestaña: Catálogo de libros ----------
class TabLibros(ttk.Frame):
    def __init__(self, padre):
        super().__init__(padre)
        form = ttk.Frame(self)
        form.pack(pady=5)
        self.titulo = campo(form, "Título:", 0)
        self.autor = campo(form, "Autor:", 1)
        self.categoria = campo(form, "Categoría:", 2)
        self.ejemplares = campo(form, "Ejemplares:", 3)
        self.ejemplares.configure(width=6)
        ttk.Button(form, text="Registrar", command=self.registrar).grid(row=0, column=8, padx=5)
        busqueda = ttk.Frame(self)
        busqueda.pack(pady=5)
        self.texto = campo(busqueda, "Buscar:", 0)
        ttk.Button(busqueda, text="Buscar", command=self.actualizar).grid(row=0, column=2, padx=5)
        ttk.Button(busqueda, text="Eliminar seleccionado", command=self.eliminar).grid(row=0, column=3, padx=5)
        self.tabla = crear_tabla(self, ("ID", "Título", "Autor", "Categoría", "Disponibles", "Total"))
        self.actualizar()

    def actualizar(self):
        t = f"%{self.texto.get().strip()}%"
        llenar(self.tabla, consulta("SELECT id, titulo, autor, categoria, disponibles, ejemplares "
                                    "FROM libros WHERE titulo LIKE ? OR autor LIKE ? "
                                    "OR categoria LIKE ?", (t, t, t)))

    def registrar(self):
        try:
            n = int(self.ejemplares.get())
            assert n > 0
        except (ValueError, AssertionError):
            messagebox.showwarning("Dato inválido", "Ejemplares debe ser un número mayor a 0.")
            return
        titulo = self.titulo.get().strip()
        if not titulo:
            messagebox.showwarning("Faltan datos", "El título es obligatorio.")
            return
        ejecutar("INSERT INTO libros(titulo, autor, categoria, ejemplares, disponibles) "
                 "VALUES(?,?,?,?,?)",
                 (titulo, self.autor.get().strip(), self.categoria.get().strip(), n, n))
        for e in (self.titulo, self.autor, self.categoria, self.ejemplares):
            e.delete(0, "end")
        self.actualizar()

    def eliminar(self):
        id_libro = seleccionado(self.tabla)
        if id_libro is None:
            return
        if consulta("SELECT 1 FROM prestamos WHERE id_libro=?", (id_libro,)):
            messagebox.showwarning("No se puede", "Este libro tiene préstamos registrados,\n"
                                   "no se puede eliminar.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este libro definitivamente?"):
            ejecutar("DELETE FROM libros WHERE id=?", (id_libro,))
            self.actualizar()


# ---------- Pestaña: Préstamos, devoluciones y multas ----------
class TabPrestamos(ttk.Frame):
    def __init__(self, padre):
        super().__init__(padre)
        form = ttk.Frame(self)
        form.pack(pady=5)
        ttk.Label(form, text="Lector:").grid(row=0, column=0, padx=5)
        self.lector = ttk.Combobox(form, width=28, state="readonly")
        self.lector.grid(row=0, column=1)
        ttk.Label(form, text="Libro:").grid(row=0, column=2, padx=5)
        self.libro = ttk.Combobox(form, width=34, state="readonly")
        self.libro.grid(row=0, column=3)
        ttk.Button(form, text="Prestar", command=self.prestar).grid(row=0, column=4, padx=5)
        acciones = ttk.Frame(self)
        acciones.pack()
        ttk.Button(acciones, text="Devolver seleccionado", command=self.devolver).pack(side="left", padx=5)
        ttk.Button(acciones, text="Renovar seleccionado", command=self.renovar).pack(side="left", padx=5)
        self.tabla = crear_tabla(self, ("ID", "Lector", "Libro", "Fecha límite", "Estado"))
        self.actualizar()

    def actualizar(self):
        self.lector["values"] = [f"{r[0]} - {r[1]}" for r in
                                 consulta("SELECT id, nombre FROM lectores WHERE activo=1")]
        self.libro["values"] = [f"{r[0]} - {r[1]} ({r[2]} disp.)" for r in
                                consulta("SELECT id, titulo, disponibles FROM libros "
                                         "WHERE disponibles > 0")]
        hoy = date.today().isoformat()
        filas = []
        for p in consulta("SELECT p.id, r.nombre, l.titulo, p.fecha_limite, "
                          "p.fecha_devolucion, p.multa FROM prestamos p "
                          "JOIN lectores r ON r.id = p.id_lector "
                          "JOIN libros l ON l.id = p.id_libro ORDER BY p.id DESC"):
            if p[4]:
                estado = f"Devuelto (multa S/ {p[5]:.2f})"
            else:
                estado = "VENCIDO" if p[3] < hoy else "Prestado"
            filas.append((p[0], p[1], p[2], p[3], estado))
        llenar(self.tabla, filas)

    def prestar(self):
        if not self.lector.get() or not self.libro.get():
            messagebox.showwarning("Faltan datos", "Elige un lector y un libro.")
            return
        id_lector = int(self.lector.get().split(" - ")[0])
        id_libro = int(self.libro.get().split(" - ")[0])
        hoy = date.today()
        limite = hoy + timedelta(days=DIAS_PRESTAMO)
        ejecutar("INSERT INTO prestamos(id_lector, id_libro, fecha_prestamo, fecha_limite) "
                 "VALUES(?,?,?,?)", (id_lector, id_libro, hoy.isoformat(), limite.isoformat()))
        ejecutar("UPDATE libros SET disponibles = disponibles - 1 WHERE id=?", (id_libro,))
        self.lector.set("")
        self.libro.set("")
        self.actualizar()
        messagebox.showinfo("Préstamo", f"Registrado. Devolver antes del {limite}.")

    def _activo(self, id_prestamo):
        return consulta("SELECT id_libro, fecha_limite FROM prestamos "
                        "WHERE id=? AND fecha_devolucion IS NULL", (id_prestamo,))

    def devolver(self):
        id_prestamo = seleccionado(self.tabla)
        if id_prestamo is None:
            return
        datos = self._activo(id_prestamo)
        if not datos:
            messagebox.showinfo("Aviso", "Ese préstamo ya fue devuelto.")
            return
        hoy = date.today()
        retraso = max(0, (hoy - date.fromisoformat(datos[0][1])).days)
        multa = retraso * MULTA_POR_DIA
        ejecutar("UPDATE prestamos SET fecha_devolucion=?, multa=? WHERE id=?",
                 (hoy.isoformat(), multa, id_prestamo))
        ejecutar("UPDATE libros SET disponibles = disponibles + 1 WHERE id=?", (datos[0][0],))
        self.actualizar()
        messagebox.showinfo("Devolución", f"Días de retraso: {retraso}\nMulta: S/ {multa:.2f}")

    def renovar(self):
        id_prestamo = seleccionado(self.tabla)
        if id_prestamo is None:
            return
        datos = self._activo(id_prestamo)
        if not datos:
            messagebox.showinfo("Aviso", "Ese préstamo ya fue devuelto.")
            return
        nueva = date.fromisoformat(datos[0][1]) + timedelta(days=DIAS_PRESTAMO)
        ejecutar("UPDATE prestamos SET fecha_limite=? WHERE id=?", (nueva.isoformat(), id_prestamo))
        self.actualizar()
        messagebox.showinfo("Renovación", f"Nueva fecha límite: {nueva}")


# ---------- Pestaña: Reportes ----------
class TabReportes(ttk.Frame):
    def __init__(self, padre):
        super().__init__(padre)
        barra = ttk.Frame(self)
        barra.pack(pady=5)
        ttk.Button(barra, text="Libros más prestados", command=self.mas_prestados).grid(row=0, column=0, padx=5)
        ttk.Button(barra, text="Lectores morosos", command=self.morosos).grid(row=0, column=1, padx=5)
        fechas = ttk.Frame(self)
        fechas.pack(pady=5)
        self.desde = campo(fechas, "Desde (AAAA-MM-DD):", 0)
        self.hasta = campo(fechas, "Hasta:", 1)
        ttk.Button(fechas, text="Préstamos por fecha", command=self.por_fecha).grid(row=0, column=4, padx=5)
        self.salida = tk.Text(self, height=18, state="disabled")
        self.salida.pack(fill="both", expand=True, padx=10, pady=5)

    def actualizar(self):
        pass

    def mostrar(self, titulo, lineas):
        self.salida.configure(state="normal")
        self.salida.delete("1.0", "end")
        self.salida.insert("end", f"--- {titulo} ---\n")
        self.salida.insert("end", "\n".join(lineas) if lineas else "Sin resultados.")
        self.salida.configure(state="disabled")

    def mas_prestados(self):
        filas = consulta("SELECT l.titulo, COUNT(*) AS n FROM prestamos p "
                         "JOIN libros l ON l.id = p.id_libro GROUP BY l.id "
                         "ORDER BY n DESC LIMIT 5")
        self.mostrar("Libros más prestados", [f"{f[0]}: {f[1]} préstamos" for f in filas])

    def morosos(self):
        filas = consulta("SELECT r.nombre, l.titulo, p.fecha_limite FROM prestamos p "
                         "JOIN lectores r ON r.id = p.id_lector JOIN libros l ON l.id = p.id_libro "
                         "WHERE p.fecha_devolucion IS NULL AND p.fecha_limite < ?",
                         (date.today().isoformat(),))
        self.mostrar("Lectores morosos", [f"{f[0]} debe '{f[1]}' (venció el {f[2]})" for f in filas])

    def por_fecha(self):
        filas = consulta("SELECT p.id, r.nombre, l.titulo, p.fecha_prestamo FROM prestamos p "
                         "JOIN lectores r ON r.id = p.id_lector JOIN libros l ON l.id = p.id_libro "
                         "WHERE p.fecha_prestamo BETWEEN ? AND ?",
                         (self.desde.get().strip(), self.hasta.get().strip()))
        self.mostrar("Préstamos por fecha", [f"#{f[0]} {f[1]} - {f[2]} ({f[3]})" for f in filas])


# ---------- Ventana principal y login ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BiblioTec - Sistema de Biblioteca")
        self.geometry("900x520")
        self.mostrar_login()

    def mostrar_login(self):
        self.marco = ttk.Frame(self)
        self.marco.pack(expand=True)
        ttk.Label(self.marco, text="BiblioTec", font=("Arial", 22, "bold")).grid(row=0, columnspan=2, pady=15)
        ttk.Label(self.marco, text="Usuario:").grid(row=1, column=0, pady=5)
        self.usuario = ttk.Entry(self.marco)
        self.usuario.grid(row=1, column=1)
        ttk.Label(self.marco, text="Clave:").grid(row=2, column=0, pady=5)
        self.clave = ttk.Entry(self.marco, show="*")
        self.clave.grid(row=2, column=1)
        ttk.Button(self.marco, text="Ingresar", command=self.entrar).grid(row=3, columnspan=2, pady=15)
        self.bind("<Return>", lambda e: self.entrar())

    def entrar(self):
        fila = consulta("SELECT rol FROM usuarios WHERE usuario=? AND clave=?",
                        (self.usuario.get().strip(), self.clave.get().strip()))
        if not fila:
            messagebox.showerror("Error", "Usuario o clave incorrectos.")
            return
        self.unbind("<Return>")
        self.marco.destroy()
        self.mostrar_sistema(fila[0][0])

    def mostrar_sistema(self, rol):
        cuaderno = ttk.Notebook(self)
        cuaderno.pack(fill="both", expand=True)
        self.pestanas = []
        if rol == "bibliotecario":
            self.pestanas += [("Lectores", TabLectores(cuaderno)),
                              ("Libros", TabLibros(cuaderno)),
                              ("Préstamos", TabPrestamos(cuaderno))]
        self.pestanas.append(("Reportes", TabReportes(cuaderno)))
        for nombre, pestana in self.pestanas:
            cuaderno.add(pestana, text=nombre)
        cuaderno.bind("<<NotebookTabChanged>>",
                      lambda e: [p.actualizar() for _, p in self.pestanas])


if __name__ == "__main__":
    crear_tablas()
    App().mainloop()
