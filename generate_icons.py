from PIL import Image, ImageDraw

def create_icon(filename, text, color):
    # Cria imagem 16x16 (padrão CKEditor)
    img = Image.new('RGB', (16, 16), color='white')
    d = ImageDraw.Draw(img)
    # Borda preta
    d.rectangle([0, 0, 15, 15], outline='black')
    
    # Desenha uma letra simples no meio (simulando um icone)
    # Como nao sabemos fontes, vamos desenhar formas simples
    if text == 'I': # Instagram
        # Um circulo e um ponto
        d.ellipse([2, 2, 13, 13], outline=color, width=2)
        d.point([8, 8], fill=color)
    elif text == 'A': # Ads
        # Um cifrão tosco ou linhas de texto
        d.rectangle([3, 4, 12, 5], fill=color)
        d.rectangle([3, 7, 12, 8], fill=color)
        d.rectangle([3, 10, 12, 11], fill=color)

    img.save(f'c:/oxira/blog/static/ckeditor/ckeditor/plugins/oxiraembed/icons/{filename}')
    print(f'Criado {filename}')

if __name__ == "__main__":
    create_icon('instagram.png', 'I', '#C13584') # Cor do IG
    create_icon('adbreak.png', 'A', '#000000')   # Preto para contraste máximo
