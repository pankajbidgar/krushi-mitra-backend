def get_new_order_email(farmer_name, order_id, total_amount, buyer_name):
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; background: #f4f7ff; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 20px;">
                <h2 style="color: #2e7d32;">🌾 नवीन ऑर्डर आला!</h2>
                <p>नमस्कार {farmer_name},</p>
                <p>तुमच्या उत्पादनावर नवीन ऑर्डर प्राप्त झाला आहे.</p>
                <p><strong>ऑर्डर क्रमांक:</strong> #{order_id}</p>
                <p><strong>एकूण रक्कम:</strong> ₹{total_amount}</p>
                <p><strong>खरेदीदार:</strong> {buyer_name}</p>
                <p>कृपया लॉगिन करून ऑर्डरची पुष्टी करा.</p>
                <a href="http://localhost:3000/farmer/orders" style="background: #2e7d32; color: white; padding: 8px 16px; text-decoration: none; border-radius: 30px;">ऑर्डर बघा</a>
                <hr style="margin: 20px 0;">
                <p style="color: #888;">शेतकरी बाजार</p>
            </div>
        </body>
    </html>
    """

def get_order_status_email(buyer_name, order_id, status, new_status):
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; background: #f4f7ff; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 20px;">
                <h2 style="color: #2e7d32;">📦 ऑर्डर स्टेटस बदलला</h2>
                <p>नमस्कार {buyer_name},</p>
                <p>तुमची ऑर्डर #{order_id} आता <strong>{new_status}</strong> झाली आहे.</p>
                <a href="http://localhost:3000/buyer/orders" style="background: #2e7d32; color: white; padding: 8px 16px; text-decoration: none; border-radius: 30px;">ऑर्डर बघा</a>
                <hr>
                <p style="color: #888;">शेतकरी बाजार</p>
            </div>
        </body>
    </html>
    """

def get_welcome_email(user_name):
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; background: #f4f7ff; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 20px;">
                <h2 style="color: #2e7d32;">🌾 शेतकरी बाजार मध्ये स्वागत आहे!</h2>
                <p>नमस्कार {user_name},</p>
                <p>तुमची नोंदणी यशस्वी झाली आहे. आता तुम्ही उत्पादने खरेदी/विक्री करू शकता.</p>
                <a href="http://localhost:3000/dashboard" style="background: #2e7d32; color: white; padding: 8px 16px; text-decoration: none; border-radius: 30px;">डॅशबोर्डवर जा</a>
                <hr>
                <p style="color: #888;">शेतकरी बाजार</p>
            </div>
        </body>
    </html>
    """