document: 
	python document.py

website: 
	(\
	. webpage/bin/activate;  \
	python app.py; \
	)

main:
	python risk_assessment_library.py

test:
	python test_out.py