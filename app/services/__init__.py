"""Service layer (business logic).

Services orchestrate multiple repositories and implement the domain rules
that the original PHP ``App/Controller/Base.php`` kept in its ``precheck*``
methods (freeze, block, promised pay, real-IP, ...).
"""
