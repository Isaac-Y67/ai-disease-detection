-- =====================================================================
-- AI-Powered Early Disease Detection and Patient Risk Prediction System
-- MySQL schema (physical design, Chapter 5, Section 5.5.3)
-- Target: MySQL 8.0 (Community Server), InnoDB, utf8mb4
-- =====================================================================

CREATE DATABASE IF NOT EXISTS ai_disease_detection
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_disease_detection;

-- ---------------------------------------------------------------------
-- Roles and users
-- ---------------------------------------------------------------------
CREATE TABLE roles (
  role_id    TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  role_name  VARCHAR(40)      NOT NULL,
  PRIMARY KEY (role_id),
  UNIQUE KEY uq_roles_name (role_name)
) ENGINE=InnoDB;

CREATE TABLE users (
  user_id        INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  full_name      VARCHAR(100)     NOT NULL,
  email          VARCHAR(120)     NOT NULL,
  password_hash  VARCHAR(255)     NOT NULL,   -- salted hash, never the plain password
  role_id        TINYINT UNSIGNED NOT NULL,
  is_active      TINYINT(1)       NOT NULL DEFAULT 1,
  created_at     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_role (role_id),
  CONSTRAINT fk_users_role FOREIGN KEY (role_id)
    REFERENCES roles (role_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Patients (anonymized: a code only, no names or contact details)
-- ---------------------------------------------------------------------
CREATE TABLE patients (
  patient_id     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  patient_code   VARCHAR(20)   NOT NULL,
  sex            ENUM('Male','Female') NOT NULL,
  birth_year     SMALLINT UNSIGNED NULL,
  registered_by  INT UNSIGNED  NOT NULL,
  registered_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (patient_id),
  UNIQUE KEY uq_patients_code (patient_code),
  KEY idx_patients_registered_by (registered_by),
  CONSTRAINT fk_patients_user FOREIGN KEY (registered_by)
    REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Disease modules and the model versions trained for them
-- ---------------------------------------------------------------------
CREATE TABLE disease_modules (
  module_id      TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  module_code    VARCHAR(30)      NOT NULL,
  module_name    VARCHAR(80)      NOT NULL,
  feature_count  TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (module_id),
  UNIQUE KEY uq_modules_code (module_code)
) ENGINE=InnoDB;

CREATE TABLE model_versions (
  model_version_id INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  module_id        TINYINT UNSIGNED NOT NULL,
  algorithm        VARCHAR(40)      NOT NULL,
  trained_on       DATE             NOT NULL,
  artifact_file    VARCHAR(120)     NOT NULL,
  is_active        TINYINT(1)       NOT NULL DEFAULT 1,
  PRIMARY KEY (model_version_id),
  KEY idx_model_versions_module (module_id),
  CONSTRAINT fk_model_versions_module FOREIGN KEY (module_id)
    REFERENCES disease_modules (module_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Assessments (one row per prediction made)
-- ---------------------------------------------------------------------
CREATE TABLE assessments (
  assessment_id     BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
  patient_id        INT UNSIGNED     NOT NULL,
  model_version_id  INT UNSIGNED     NOT NULL,
  performed_by      INT UNSIGNED     NOT NULL,
  input_data        JSON             NOT NULL,   -- module-specific predictors
  prediction        TINYINT UNSIGNED NOT NULL,
  probability       DECIMAL(5,4)     NOT NULL,
  risk_level        ENUM('Low','Moderate','High') NOT NULL,
  created_at        DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (assessment_id),
  KEY idx_assessments_patient (patient_id),
  KEY idx_assessments_model (model_version_id),
  KEY idx_assessments_user (performed_by),
  KEY idx_assessments_created (created_at),
  CONSTRAINT chk_assessments_prediction CHECK (prediction IN (0, 1)),
  CONSTRAINT fk_assessments_patient FOREIGN KEY (patient_id)
    REFERENCES patients (patient_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_assessments_model FOREIGN KEY (model_version_id)
    REFERENCES model_versions (model_version_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_assessments_user FOREIGN KEY (performed_by)
    REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Audit trail
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
  log_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     INT UNSIGNED    NULL,
  action      VARCHAR(60)     NOT NULL,
  entity      VARCHAR(40)     NULL,
  entity_id   BIGINT UNSIGNED NULL,
  ip_address  VARCHAR(45)     NULL,
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_audit_user (user_id),
  KEY idx_audit_created (created_at),
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
    REFERENCES users (user_id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------------
INSERT INTO roles (role_name) VALUES ('Administrator'), ('Healthcare Professional');

INSERT INTO disease_modules (module_code, module_name, feature_count) VALUES
  ('heart',        'Heart disease', 13),
  ('diabetes',     'Diabetes',       8),
  ('hypertension', 'Hypertension',  14),
  ('lung_cancer',  'Lung cancer',   15);

-- Register the trained models (adjust trained_on to the real training dates).
INSERT INTO model_versions (module_id, algorithm, trained_on, artifact_file)
SELECT module_id, 'Support Vector Machine', CURDATE(), 'heart_disease_model.pkl'
  FROM disease_modules WHERE module_code = 'heart';
INSERT INTO model_versions (module_id, algorithm, trained_on, artifact_file)
SELECT module_id, 'Random Forest', CURDATE(), 'diabetes_model.pkl'
  FROM disease_modules WHERE module_code = 'diabetes';
INSERT INTO model_versions (module_id, algorithm, trained_on, artifact_file)
SELECT module_id, 'Random Forest', CURDATE(), 'hypertension_model.pkl'
  FROM disease_modules WHERE module_code = 'hypertension';
INSERT INTO model_versions (module_id, algorithm, trained_on, artifact_file)
SELECT module_id, 'Support Vector Machine', CURDATE(), 'lung_cancer_model.pkl'
  FROM disease_modules WHERE module_code = 'lung_cancer';
