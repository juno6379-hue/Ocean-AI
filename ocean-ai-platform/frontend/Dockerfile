FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Vite 개발 서버를 외부에서 접근할 수 있도록 --host 옵션 추가 설정은 package.json의 dev 스크립트에서 진행
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
