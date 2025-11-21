import customtkinter
import tkinter

customtkinter.set_appearance_mode("dark")


app = customtkinter.CTk()
app.title("really?123")
app.geometry("800x600")
def func():
    print("pressed")
button = customtkinter.CTkButton(master=app, text="press it", command=func)
button.place(relx=0.5, rely=0.7, anchor=tkinter.CENTER)
app.mainloop()