import customtkinter
import tkinter
from ui.tabbar import TabBar

customtkinter.set_appearance_mode("light")


app = customtkinter.CTk()
app.title("really?123")
app.geometry("800x600")
button2 = customtkinter.CTkButton(master=app, text="another")
def func():
    print("pressed")
    button2.place(relx=0.3, rely=0.2, anchor=tkinter.CENTER)
button = customtkinter.CTkButton(master=app, text="press it", command=func)
button.place(relx=0.5, rely=0.7, anchor=tkinter.CENTER)

def func2(s: str):
    pass
# menu = customtkinter.CTkOptionMenu(master=app, values=["123", "456", "789"], button_color=)
# menu.set("123")
# menu.place(relx=0.1, rely=0.1, anchor=tkinter.CENTER)
page1 = customtkinter.CTkFrame(master=app)
customtkinter.CTkLabel(master=page1, text="內容 1").place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        # self.register_frame("項目1", page1)

page2 = customtkinter.CTkFrame(master=app)
customtkinter.CTkLabel(master=page2, text="內容 2").place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
        # self.register_frame("項目二", page2)

page3 = customtkinter.CTkFrame(master=app)
customtkinter.CTkLabel(master=page3, text="內容 3").place(relx=0.5, rely=0.4, anchor=tkinter.CENTER)
# self.register_frame("項目三", page3)

        # 建 TabBar，並讓 TabBar 的按鈕在點擊時呼叫 self.show_tab (或你現有的 update_window_state)
tabbar = TabBar(master=app, command=func2)
        # register tabs to TabBar (也會自動顯示 default)
tabbar.add_tab("項目1", page1, default=True)
tabbar.add_tab("項目二", page2)
tabbar.add_tab("項目三", page3)
tabbar.show("項目二")


app.mainloop()