CREATE TABLE bank(
    branch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	b_code VARCHAR,
	b_city TEXT,
	b_region TEXT,
	b_country TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customer_data(
	customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	acc_no VARCHAR,
	customer_name TEXT,
	age INT,
	customer_type TEXT,
	city TEXT,
	region TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transaction_data(
	transc_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	transc_ref VARCHAR,
	customer_id BIGINT,
	branch_id BIGINT,
	FOREIGN KEY (customer_id) REFERENCES customer_data(customer_id),
	FOREIGN KEY (branch_id) REFERENCES bank(branch_id),
	acc_type TEXT,
	total_bal NUMERIC,
	transc_amount NUMERIC,
	invest_amount NUMERIC,
	invest_type TEXT,
	transac_date DATE,
	datares_loc TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_log(
	log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	table_name TEXT,
	record_id BIGINT,
	action TEXT,
	old_value TEXT,
	new_value TEXT,
	residency_flag TEXT,
	performed_by TEXT,
	logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_class (
	class_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	table_name TEXT,
	column_name TEXT,
	data_classification TEXT
);