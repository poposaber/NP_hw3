import customtkinter
import tkinter

customtkinter.set_appearance_mode("dark")


app = customtkinter.CTk()
app.title("really?123")
app.geometry("800x600")
button2 = customtkinter.CTkButton(master=app, text="another")
def func():
    print("pressed")
    button2.place(relx=0.3, rely=0.2, anchor=tkinter.CENTER)
button = customtkinter.CTkButton(master=app, text="press it", command=func)
button.place(relx=0.5, rely=0.7, anchor=tkinter.CENTER)
app.mainloop()