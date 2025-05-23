"""
Módulo para interactuar con la API de Groq.
"""
import os
import time
import json
import streamlit as st
from groq import Groq
from src.api.base_client import BaseAPIClient

class GroqClient(BaseAPIClient):
    """
    Cliente para interactuar con la API de Groq.
    Implementa la interfaz definida en BaseAPIClient.
    """
    def __init__(self, api_key=None, logger=None):
        """
        Inicializa el cliente de Groq.
        
        Args:
            api_key (str, optional): Clave API de Groq. Si no se proporciona, 
                                     se intenta obtener de las variables de entorno.
            logger (logging.Logger, optional): Logger para registrar información.
        """
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.logger = logger
        self.client = None
        
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        
    def is_configured(self):
        """
        Verifica si el cliente está configurado correctamente.
        
        Returns:
            bool: True si el cliente está configurado, False en caso contrario.
        """
        return self.client is not None and self.api_key is not None
    
    def set_api_key(self, api_key):
        """
        Establece la clave API y reconfigura el cliente.
        
        Args:
            api_key (str): Clave API de Groq.
        """
        self.api_key = api_key
        os.environ["GROQ_API_KEY"] = api_key
        self.client = Groq(api_key=self.api_key)
        
        if self.logger:
            self.logger.info("API key configurada")
    
    # Función cacheada para obtener respuestas que no cambiarán con los mismos parámetros
    @st.cache_data(ttl=3600, show_spinner=False)
    def _cached_api_call(self, model, messages_str, temperature, max_tokens):
        """
        Realiza una llamada a la API con caché.
        
        Args:
            model (str): ID del modelo a utilizar.
            messages_str (str): Representación en string de los mensajes (para caché).
            temperature (float): Temperatura para la generación.
            max_tokens (int): Número máximo de tokens en la respuesta.
            
        Returns:
            str: Contenido de la respuesta o mensaje de error.
        """
        try:
            # Convertir la representación de string a lista de mensajes
            import json
            messages = json.loads(messages_str)
            
            if self.logger:
                self.logger.info(f"Llamada a API CACHEADA con modelo: {model}")
            
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            elapsed_time = time.time() - start_time
            
            if self.logger:
                self.logger.info(f"Respuesta cacheada recibida en {elapsed_time:.2f} segundos")
            
            return response.choices[0].message.content
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error en llamada API cacheada: {str(e)}")
            return f"Error al llamar a la API: {str(e)}"
    
    def get_cached_response(self, model, messages, temperature, max_tokens):
        """
        Obtiene una respuesta cacheada para parámetros específicos.
        
        Args:
            model (str): ID del modelo a utilizar.
            messages (list): Lista de mensajes para la conversación.
            temperature (float): Temperatura para la generación.
            max_tokens (int): Número máximo de tokens en la respuesta.
            
        Returns:
            str: Contenido de la respuesta o mensaje de error.
        """
        if not self.is_configured():
            return "Error: API no configurada. Por favor, proporciona una clave API."
        
        try:
            # Convertir mensajes a string para la caché
            import json
            messages_str = json.dumps(messages)
            
            if self.logger:
                self.logger.info(f"Preparando llamada cacheada: {model}, temperatura: {temperature}, max_tokens: {max_tokens}")
            
            # Usar la función cacheada
            return self._cached_api_call(model, messages_str, temperature, max_tokens)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error al preparar llamada cacheada: {str(e)}")
            return f"Error al llamar a la API: {str(e)}"
    
    def generate_streaming_response(self, model, messages, temperature, max_tokens, callback=None):
        """
        Genera una respuesta en streaming para una experiencia más interactiva.
        
        Args:
            model (str): ID del modelo a utilizar.
            messages (list): Lista de mensajes para la conversación.
            temperature (float): Temperatura para la generación.
            max_tokens (int): Número máximo de tokens en la respuesta.
            callback (callable, optional): Función de callback para cada fragmento de respuesta.
            
        Returns:
            dict: Diccionario con la respuesta completa generada y las herramientas ejecutadas.
                 Formato: {"content": str, "executed_tools": list}
        """
        if not self.is_configured():
            return {"content": "Error: API no configurada. Por favor, proporciona una clave API.", "executed_tools": []}
        
        try:
            if self.logger:
                self.logger.info(f"Iniciando llamada a API (streaming) con modelo: {model}")
                self.logger.info(f"Parámetros: temperatura={temperature}, max_tokens={max_tokens}")
            
            start_time = time.time()
            
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            if self.logger:
                self.logger.info("Conexión establecida, comenzando streaming...")
            
            full_response = ""
            executed_tools = []
            chunk_count = 0
            
            for chunk in stream:
                chunk_count += 1
                
                # Procesar contenido del mensaje
                if hasattr(chunk.choices[0].delta, "content") and chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    
                    if callback:
                        callback(full_response)
                
                # Procesar herramientas ejecutadas
                if hasattr(chunk.choices[0].delta, "executed_tools") and chunk.choices[0].delta.executed_tools:
                    # Convertir a diccionario para facilitar el manejo
                    for tool in chunk.choices[0].delta.executed_tools:
                        tool_dict = tool.model_dump() if hasattr(tool, "model_dump") else tool
                        executed_tools.append(tool_dict)
                        if self.logger:
                            self.logger.info(f"Herramienta ejecutada: {tool_dict.get('type', 'desconocida')}")
            
            elapsed_time = time.time() - start_time
            
            if self.logger:
                self.logger.info(f"Streaming completado: {chunk_count} chunks recibidos en {elapsed_time:.2f} segundos")
                if executed_tools:
                    self.logger.info(f"Herramientas ejecutadas: {len(executed_tools)}")
            
            return {
                "content": full_response,
                "executed_tools": executed_tools
            }
        except Exception as e:
            error_msg = f"Error al llamar a la API: {str(e)}"
            
            if self.logger:
                self.logger.error(error_msg)
                self.logger.exception("Detalles del error:")
            
            return {
                "content": error_msg,
                "executed_tools": []
            }
    
    def generate_response_with_tools(self, model, messages, tools, temperature, max_tokens, callback=None, tool_choice="auto"):
        """
        Genera una respuesta utilizando herramientas definidas (tools).
        
        Args:
            model (str): ID del modelo a utilizar.
            messages (list): Lista de mensajes para la conversación.
            tools (list): Lista de herramientas disponibles para el modelo.
            temperature (float): Temperatura para la generación.
            max_tokens (int): Número máximo de tokens en la respuesta.
            callback (callable, optional): Función de callback para cada fragmento de respuesta.
            tool_choice (str, optional): Estrategia para elegir herramientas. Por defecto "auto".
            
        Returns:
            dict: Diccionario con la respuesta y las llamadas a herramientas.
        """
        if not self.is_configured():
            return {"content": "Error: API no configurada. Por favor, proporciona una clave API.", "tool_calls": []}
        
        try:
            if self.logger:
                self.logger.info(f"Iniciando llamada a API con herramientas (modelo: {model})")
                self.logger.info(f"Parámetros: temperatura={temperature}, max_tokens={max_tokens}")
                self.logger.info(f"Herramientas disponibles: {len(tools)}")
            
            start_time = time.time()
            
            # Realizar la llamada a la API con las herramientas definidas
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            elapsed_time = time.time() - start_time
            
            if self.logger:
                self.logger.info(f"Respuesta recibida en {elapsed_time:.2f} segundos")
            
            # Extraer la respuesta y las llamadas a herramientas
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls if hasattr(response_message, "tool_calls") else []
            
            if tool_calls and self.logger:
                self.logger.info(f"El modelo ha realizado {len(tool_calls)} llamadas a herramientas")
            
            return {
                "message": response_message,
                "content": response_message.content,
                "tool_calls": tool_calls
            }
            
        except Exception as e:
            error_msg = f"Error al llamar a la API con herramientas: {str(e)}"
            
            if self.logger:
                self.logger.error(error_msg)
                self.logger.exception("Detalles del error:")
            
            return {
                "content": error_msg,
                "tool_calls": []
            }
    
    def process_tool_calls(self, model, messages, tool_calls, available_functions, temperature, max_tokens):
        """
        Procesa las llamadas a herramientas y obtiene una respuesta final.
        
        Args:
            model (str): ID del modelo a utilizar.
            messages (list): Lista de mensajes para la conversación.
            tool_calls (list): Lista de llamadas a herramientas realizadas por el modelo.
            available_functions (dict): Diccionario con las funciones disponibles.
            temperature (float): Temperatura para la generación.
            max_tokens (int): Número máximo de tokens en la respuesta.
            
        Returns:
            dict: Diccionario con la respuesta final y los resultados de las herramientas.
        """
        if not self.is_configured():
            return {"content": "Error: API no configurada. Por favor, proporciona una clave API.", "tool_results": []}
        
        try:
            if self.logger:
                self.logger.info(f"Procesando {len(tool_calls)} llamadas a herramientas")
            
            # Añadir el mensaje del asistente con las llamadas a herramientas
            assistant_message = messages[-1] if messages and messages[-1]["role"] == "assistant" else None
            if not assistant_message:
                # Crear un nuevo mensaje del asistente si no existe
                assistant_message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls
                }
                messages.append(assistant_message)
            
            # Procesar cada llamada a herramienta
            tool_results = []
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if self.logger:
                    self.logger.info(f"Ejecutando función: {function_name} con argumentos: {function_args}")
                
                # Verificar si la función existe
                if function_name not in available_functions:
                    error_result = {
                        "success": False,
                        "error": f"Función {function_name} no encontrada"
                    }
                    tool_results.append(error_result)
                    
                    # Añadir mensaje de error a la conversación
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(error_result)
                    })
                    continue
                
                # Ejecutar la función
                function_to_call = available_functions[function_name]
                try:
                    function_response = function_to_call(**function_args)
                    tool_results.append(function_response)
                    
                    # Añadir resultado a la conversación
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_response)
                    })
                except Exception as e:
                    error_result = {
                        "success": False,
                        "error": f"Error al ejecutar {function_name}: {str(e)}"
                    }
                    tool_results.append(error_result)
                    
                    # Añadir mensaje de error a la conversación
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(error_result)
                    })
            
            # Realizar una segunda llamada a la API con los resultados de las herramientas
            if self.logger:
                self.logger.info("Realizando segunda llamada a la API con los resultados de las herramientas")
            
            second_response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            final_response = second_response.choices[0].message.content
            
            if self.logger:
                self.logger.info("Segunda llamada completada, respuesta final generada")
            
            return {
                "content": final_response,
                "tool_results": tool_results
            }
            
        except Exception as e:
            error_msg = f"Error al procesar llamadas a herramientas: {str(e)}"
            
            if self.logger:
                self.logger.error(error_msg)
                self.logger.exception("Detalles del error:")
            
            return {
                "content": error_msg,
                "tool_results": []
            }
    
    def generate_response_with_image(self, model, messages, image_data, temperature, max_tokens, callback=None):
        """
        Genera una respuesta basada en texto e imagen.
        
        Args:
            model (str): ID del modelo a utilizar.
            messages (list): Lista de mensajes para la conversación.
            image_data (dict): Datos de la imagen (URL o base64).
            temperature (float): Temperatura para la generación.
            max_tokens (int): Número máximo de tokens en la respuesta.
            callback (callable, optional): Función de callback para cada fragmento de respuesta.
            
        Returns:
            dict: Diccionario con la respuesta completa generada y metadatos.
        """
        if not self.is_configured():
            return {"content": "Error: API no configurada. Por favor, proporciona una clave API.", "executed_tools": []}
        
        try:
            if self.logger:
                self.logger.info(f"Iniciando llamada a API con imagen (modelo: {model})")
                self.logger.info(f"Parámetros: temperatura={temperature}, max_tokens={max_tokens}")
            
            # Obtener el último mensaje para combinarlo con la imagen
            last_message = None
            if messages and len(messages) > 0:
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        last_message = msg
                        break
            
            if not last_message:
                last_message = {"role": "user", "content": "Describe esta imagen en detalle."}
            
            # Preparar el contenido del mensaje con imagen
            content = [
                {"type": "text", "text": last_message.get("content", "Describe esta imagen en detalle.")}
            ]
            
            # Añadir la imagen según su tipo (URL o base64)
            if "url" in image_data:
                image_url = image_data["url"]
                if self.logger:
                    self.logger.info(f"Usando imagen desde URL: {image_url}")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })
            elif "base64" in image_data:
                # Verificar el tamaño de la imagen en base64
                base64_size_mb = len(image_data["base64"]) * 3 / 4 / 1024 / 1024  # Estimación aproximada
                if self.logger:
                    self.logger.info(f"Tamaño aproximado de la imagen en base64: {base64_size_mb:.2f}MB")
                
                if base64_size_mb > 4:
                    if self.logger:
                        self.logger.warning(f"La imagen es demasiado grande ({base64_size_mb:.2f}MB). Groq limita a 4MB para imágenes base64.")
                    raise ValueError(f"La imagen es demasiado grande ({base64_size_mb:.2f}MB). Groq limita a 4MB para imágenes base64.")
                
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data['base64']}"}
                })
            else:
                raise ValueError("Los datos de imagen deben contener 'url' o 'base64'")
            
            # Preparar los mensajes para la API
            api_messages = []
            
            # Incluir el mensaje del sistema si existe
            for msg in messages:
                if msg.get("role") == "system":
                    api_messages.append(msg)
                    break
            
            # Añadir mensajes anteriores (excepto el último mensaje del usuario)
            for msg in messages:
                if msg.get("role") != "system" and msg != last_message:
                    api_messages.append(msg)
            
            # Añadir el mensaje con la imagen
            api_messages.append({
                "role": "user",
                "content": content
            })
            
            start_time = time.time()
            
            # Imprimir los mensajes para depuración
            if self.logger:
                self.logger.info(f"Enviando {len(api_messages)} mensajes a la API de Groq")
                for i, msg in enumerate(api_messages):
                    role = msg.get("role", "unknown")
                    if isinstance(msg.get("content"), list):
                        content_types = [c.get("type", "unknown") for c in msg.get("content", [])]
                        self.logger.info(f"Mensaje {i}: role={role}, content_types={content_types}")
                    else:
                        self.logger.info(f"Mensaje {i}: role={role}, content=texto")
            
            # Llamar a la API con streaming
            try:
                stream = self.client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )
            except Exception as e:
                error_msg = f"Error al llamar a la API de Groq: {str(e)}"
                if self.logger:
                    self.logger.error(error_msg)
                    self.logger.exception("Detalles del error:")
                raise Exception(error_msg)
            
            if self.logger:
                self.logger.info("Conexión establecida, comenzando streaming con imagen...")
            
            full_response = ""
            executed_tools = []
            chunk_count = 0
            
            for chunk in stream:
                chunk_count += 1
                
                # Procesar contenido del mensaje
                if hasattr(chunk.choices[0].delta, "content") and chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    
                    if callback:
                        callback(full_response)
                
                # Procesar herramientas ejecutadas
                if hasattr(chunk.choices[0].delta, "executed_tools") and chunk.choices[0].delta.executed_tools:
                    # Convertir a diccionario para facilitar el manejo
                    for tool in chunk.choices[0].delta.executed_tools:
                        tool_dict = tool.model_dump() if hasattr(tool, "model_dump") else tool
                        executed_tools.append(tool_dict)
                        if self.logger:
                            self.logger.info(f"Herramienta ejecutada: {tool_dict.get('type', 'desconocida')}")
            
            elapsed_time = time.time() - start_time
            
            if self.logger:
                self.logger.info(f"Streaming con imagen completado: {chunk_count} chunks recibidos en {elapsed_time:.2f} segundos")
            
            return {
                "content": full_response,
                "executed_tools": executed_tools,
                "image_processed": True
            }
            
        except Exception as e:
            error_msg = f"Error al procesar imagen: {str(e)}"
            
            if self.logger:
                self.logger.error(error_msg)
                self.logger.exception("Detalles del error:")
            
            return {
                "content": error_msg,
                "executed_tools": [],
                "image_processed": False
            }
