import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Axios instance with default headers
const api = axios.create({
    baseURL: API_BASE_URL,
});

// Add a request interceptor to include the token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const register = async (username, password, fullName) => {
    const response = await api.post('/register', {
        username,
        hashed_password: password, // The backend expects 'hashed_password' in the model for /register
        full_name: fullName
    });
    return response.data;
};

export const login = async (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await api.post('/token', formData);
    if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token);
    }
    return response.data;
};

export const logout = () => {
    localStorage.removeItem('token');
};

export const getCurrentUser = async () => {
    const response = await api.get('/users/me');
    return response.data;
};

export const createSession = async (userName, position) => {
    const response = await api.post('/sessions', {
        user_name: userName,
        position: position
    });
    return response.data;
};

export const getQuestions = async (sessionId) => {
    const response = await api.get(`/sessions/${sessionId}/questions`);
    return response.data;
};

export const submitAnswer = async (questionId, answerText) => {
    const response = await api.post('/answers', {
        question_id: questionId,
        answer_text: answerText
    });
    return response.data;
};

export const getResults = async (sessionId) => {
    const response = await api.get(`/sessions/${sessionId}/results`);
    return response.data;
};
