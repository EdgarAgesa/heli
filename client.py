from models import Client,db
from flask_restful import Resource
from flask import Flask,make_response,request,jsonify
from flask_jwt_extended import jwt_required


class ClientResource(Resource):

    @jwt_required()
    def get(self,id=None):
        if id is None:
            clients_all = [client.to_dict() for client in Client.query.all()]
            return make_response(jsonify(clients_all),200)

        client_id = Client.query.filter_by(id=id).first().to_dict()

        return make_response(jsonify(client_id),200)
    
    @jwt_required()
    def post():
        data = request.get_json()

        if not data or "name" not in data or "email" not in data or "phone_number" not in data:
            return jsonify({"message": "Missing required fields"}),200

        new_client = Client(
            # id = data["id"],
            name = data["name"],
            email = data["email"],
            phone_number= data["phone_number"]

        )
        db.session.add(new_client)
        db.session.commit()

        new_client_dict = new_client.to_dict()

        return make_response(new_client_dict,201)
    
    @jwt_required()
    def put(self,id):
        up_client = Client.query.get(id)

        if not up_client:
            return jsonify("The id does not exist")
        
        data = request.get_json()

        up_client.name = data.get("name" ,up_client.name)
        up_client.email = data.get("email",up_client.email)
        up_client.phone_number = data.get("phone_number",up_client.phone_number)

        db.session.commit()

        return jsonify({"message":"The update was Successful"}),200
    
    @jwt_required()
    def delete(self,id):
        delete_client = Client.query.filter_by(id=id).first()

      
        if not delete_client:
            return  {f"the id {id} you want to delete does not exist"},404
        
        db.session.delete(delete_client)
        db.session.commit()

        return {f"the deletion of client {id} was successfull"},200
    
    
