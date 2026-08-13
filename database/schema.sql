CREATE DATABASE IF NOT EXISTS eventora;
USE eventora;


-- For a clean final project installation, run this schema on a new/empty event_planner database.
-- It includes the original users concept plus the complete event-management modules.

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS registrations;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(25),
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','user') NOT NULL DEFAULT 'user',
    profile_pic VARCHAR(255),
    is_verified BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(180) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(80) NOT NULL,
    venue VARCHAR(180) NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    registration_deadline DATE NULL,
    total_seats INT NOT NULL,
    seats_available INT NOT NULL,
    price DECIMAL(10,2) NOT NULL DEFAULT 0,
    banner_image VARCHAR(255) DEFAULT 'event-tech.svg',
    status ENUM('draft','published','cancelled','completed') DEFAULT 'published',
    organizer_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_date(event_date),
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    event_id INT NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ticket_id VARCHAR(40) NOT NULL UNIQUE,
    qr_code_path VARCHAR(255),
    attendance_status ENUM('present','absent') DEFAULT 'absent',
    status ENUM('confirmed','cancelled') DEFAULT 'confirmed',
    UNIQUE KEY unique_user_event(user_id,event_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_ticket(ticket_id)
);

CREATE TABLE payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    registration_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_status ENUM('pending','success','failed','refunded') DEFAULT 'pending',
    transaction_id VARCHAR(100),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_method VARCHAR(50),
    FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE
);

CREATE TABLE feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    rating TINYINT NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (rating BETWEEN 1 AND 5),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message VARCHAR(500) NOT NULL,
    type VARCHAR(50) DEFAULT 'info',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

INSERT INTO categories(name) VALUES
('Technical'),('Cultural'),('Workshop'),('Seminar'),('Sports'),('Music');

-- Admin login used by the starter project.
-- Password: admin123
INSERT INTO users(name,email,phone,password_hash,role)
VALUES ('Admin','admin@gmail.com','9999999999',
        'admin123','admin');

-- Demo events. The Flask app can create more from Admin > Create event.
INSERT INTO events(title,description,category,venue,event_date,event_time,registration_deadline,total_seats,seats_available,price,banner_image,status,organizer_id)
VALUES
('Future of AI Summit','A practical technology summit exploring AI, automation and the future of digital work.','Technical','Innovation Auditorium','2026-09-15','10:00:00','2026-09-14',250,250,499,'event-tech.svg','published',1),
('Campus Culture Night','An evening of music, dance, art and food celebrating the creativity of our campus community.','Cultural','Open Air Theatre','2026-09-22','18:30:00','2026-09-21',500,500,0,'event-culture.svg','published',1),
('Design Thinking Workshop','A hands-on workshop that turns everyday problems into useful ideas and prototypes.','Workshop','Design Lab','2026-10-04','11:00:00','2026-10-03',80,80,199,'event-workshop.svg','published',1),
('Inter-College Sports Day','A high-energy day of football, athletics and team competitions.','Sports','College Sports Ground','2026-10-12','09:00:00','2026-10-11',400,400,0,'event-sports.svg','published',1);
